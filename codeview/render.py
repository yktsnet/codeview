"""render — Syntax highlighting and Markdown/Mermaid rendering."""

from __future__ import annotations

import html
import posixpath
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import markdown
from markdown.extensions import Extension
from markdown.extensions.toc import slugify_unicode
from markdown.treeprocessors import Treeprocessor
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.util import ClassNotFound

MAX_BYTES = 512 * 1024
HIGHLIGHT_MAX_BYTES = 96 * 1024
CODE_STYLE = "github-dark"

MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def is_text(data: bytes) -> bool:
    return b"\0" not in data


def human(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def line_count(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def render_code(path: str, data: bytes) -> str:
    return render_code_lang(path, data)[0]


def render_code_lang(path: str, data: bytes) -> tuple[str, str | None]:
    """ハイライトした HTML と、言語名（ハイライトしなかったときは None）を返す。"""
    text = data.decode("utf-8", "replace")
    if len(data) > HIGHLIGHT_MAX_BYTES:
        return '<pre class="plain">' + html.escape(text) + "</pre>", None
    try:
        lexer = get_lexer_for_filename(path, text)
    except ClassNotFound:
        try:
            lexer = guess_lexer(text)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        return '<pre class="plain">' + html.escape(text) + "</pre>", None
    out = highlight(
        text, lexer, HtmlFormatter(cssclass="hl", linenos="inline", linespans="ln")
    )
    # 中身を当て推量した「テキスト」は言語として名乗らない
    lang = None if lexer.name in ("Text only", "Text") else lexer.name
    return out.replace("\n</span>", "</span>"), lang


# リンクに残してよいスキーム。javascript: や data: は外す
_LINK_SCHEMES = {"", "http", "https", "mailto"}


def _is_github(host: str) -> bool:
    host = host.lower()
    return host == "github.com" or host.endswith((".github.com", ".githubusercontent.com"))


class _Sanitize(Treeprocessor):
    """画像は文字に、危ういリンクと GitHub へのリンクはリンクでない文字にする。"""

    def run(self, root):
        for el in root.iter():
            if el.tag == "img":
                alt = el.get("alt") or "image"
                el.attrib.clear()
                el.tag = "span"
                el.set("class", "noimg")
                el.text = f"[{alt}]"
            elif el.tag == "a" and not self._keep(el.get("href", "")):
                el.attrib.clear()
                el.tag = "span"

    @staticmethod
    def _keep(href: str) -> bool:
        # ブラウザは制御文字や空白を無視して解釈するので、先に落としてから判定する
        parts = urlsplit(re.sub(r"[\x00-\x20]", "", href))
        if parts.scheme.lower() not in _LINK_SCHEMES:
            return False
        return not _is_github(parts.hostname or "")


@dataclass(frozen=True)
class LinkContext:
    """リポの Markdown の相対リンクを、生成したページへ向けるための材料。

    md_path は読んでいる `.md` のリポ内パス。解決の基準は表示するページの位置ではなく、これである。
    files と dirs は、ページになるファイルとディレクトリのリポ内パス（ルートのディレクトリは ""）。
    """

    slug: str
    md_path: str
    files: frozenset[str]
    dirs: frozenset[str]

    def resolve(self, href: str) -> str | None:
        """リポ内のページを指すリンクならサイト内の絶対パスを返す。外部・アンカーは href のまま、
        ページの無い先は None。"""
        parts = urlsplit(href.strip())
        if parts.scheme or parts.netloc or not parts.path:
            return href
        raw = unquote(parts.path)
        if raw.startswith("/"):
            target = posixpath.normpath(raw.lstrip("/") or ".")
        else:
            base = posixpath.dirname(self.md_path)
            target = posixpath.normpath(posixpath.join(base, raw))
        if target == ".":
            target = ""
        if target == ".." or target.startswith("../"):
            return None
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if not raw.endswith("/") and target in self.files:
            return f"/{self.slug}/{target}.html{frag}"
        if target in self.dirs:
            return f"/{self.slug}/" + (f"{target}/" if target else "") + frag
        return None


class _ResolveLinks(Treeprocessor):
    """リポ内を指す相対リンクを生成したページへ向け、ページの無い先はリンクでない文字にする。"""

    def __init__(self, md, links: LinkContext):
        super().__init__(md)
        self.links = links

    def run(self, root):
        for el in root.iter("a"):
            href = el.get("href")
            if href is None:
                continue
            new = self.links.resolve(href)
            if new is None:
                el.attrib.clear()
                el.tag = "span"
            else:
                el.set("href", new)


class _NoRawHtml(Extension):
    """生の HTML を解釈せず、文字として出す。信頼できない入力用。"""

    def extendMarkdown(self, md):
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        md.treeprocessors.register(_Sanitize(md), "sanitize", 5)


ISSUE_REF = re.compile(r"(?<![\w/&#\[])#(\d+)\b")
_CODE = re.compile(r"(```.*?```|~~~.*?~~~|`[^`\n]+`)", re.S)


def _link_refs(text: str, refs: dict[str, str]) -> str:
    """コードの外の `#N` を、refs にあるものはリンクにする。

    行頭の `#N` は python-markdown が見出しにしてしまうので、リンクにならなかったものは
    エスケープして文字のまま残す。
    """
    parts = _CODE.split(text)
    for i in range(0, len(parts), 2):
        seg = ISSUE_REF.sub(
            lambda m: f"[#{m.group(1)}]({refs[m.group(1)]})"
            if m.group(1) in refs
            else m.group(0),
            parts[i],
        )
        parts[i] = re.sub(r"(?m)^#(?=\d)", r"\\#", seg)
    return "".join(parts)


# 見出しがこれより少ない文書は、目次を付けても読む手間が減らない
TOC_MIN = 4


def _toc(tokens: list[dict]) -> str:
    """h1〜h3 の見出しから、畳める目次を作る。表題1つだけの h1 は数えない。"""
    flat: list[tuple[int, str, str]] = []

    def walk(items):
        for t in items:
            if t["level"] <= 3:
                flat.append((t["level"], t["id"], t["name"]))
            walk(t.get("children", []))

    walk(tokens)
    if sum(1 for lv, _, _ in flat if lv == 1) == 1:
        flat = [f for f in flat if f[0] != 1]
    if len(flat) < TOC_MIN:
        return ""
    top = min(lv for lv, _, _ in flat)
    rows = "".join(
        f'<li class="l{lv - top}"><a href="#{html.escape(i, quote=True)}">'
        f"{html.escape(html.unescape(name))}</a></li>"
        for lv, i, name in flat
    )
    return f'<details class="toc"><summary>Contents</summary><ul>{rows}</ul></details>'


def render_markdown(
    data: bytes,
    safe: bool = False,
    refs: dict[str, str] | None = None,
    links: LinkContext | None = None,
) -> tuple[str, str]:
    """safe は信頼できない入力用（生の HTML を実行せず、画像と GitHub へのリンクを出さない）。

    refs は safe のときだけ使い、`#N` から飛び先への対応を渡す。
    links は safe でないときだけ使い、リポ内への相対リンクの解決に使う。
    """
    text = data.decode("utf-8", "replace")
    if len(data) > MAX_BYTES:
        return f'<p class="empty">Too large to display ({human(len(data))})</p>', ""
    if safe:
        text = _link_refs(text, refs or {})

    mermaid_placeholders = []

    def _sub_mermaid(m):
        idx = len(mermaid_placeholders)
        mermaid_placeholders.append(m.group(1).strip())
        return f"\n\nMERMAIDPLACEHOLDERXYZ{idx}XYZ\n\n"

    preprocessed = MERMAID_BLOCK.sub(_sub_mermaid, text)

    # attr_list は {: onclick=… } で属性を差せるので、safe では使わない
    if safe:
        extensions = ["fenced_code", "tables", "sane_lists", "codehilite", _NoRawHtml()]
    else:
        extensions = [
            "fenced_code", "tables", "toc", "attr_list", "sane_lists", "codehilite"
        ]
    md = markdown.Markdown(
        extensions=extensions,
        extension_configs={
            "codehilite": {
                "css_class": "hl",
                "linenums": False,
                "guess_lang": False,
            },
            # 既定の slugify は日本語を落として `_1` のような id にするので、文字を残す
            **({} if safe else {"toc": {"slugify": slugify_unicode}}),
        },
    )
    if links is not None and not safe:
        md.treeprocessors.register(_ResolveLinks(md, links), "resolve_links", 5)
    html_content = md.convert(preprocessed)

    for idx, code in enumerate(mermaid_placeholders):
        placeholder = f"<p>MERMAIDPLACEHOLDERXYZ{idx}XYZ</p>"
        mermaid_html = f'<pre class="mermaid">{html.escape(code)}</pre>'
        if placeholder in html_content:
            html_content = html_content.replace(placeholder, mermaid_html)
        else:
            html_content = re.sub(
                rf"<p>\s*MERMAIDPLACEHOLDERXYZ{idx}XYZ\s*</p>",
                mermaid_html,
                html_content,
            )

    toc = "" if safe else _toc(getattr(md, "toc_tokens", []))
    body = f'<div class="markdown-body">{toc}{html_content}</div>'

    # build.py が書き出した同梱の mermaid を読む。通常のスクリプトなので file:// でも動く
    from codeview import build

    script = (
        f'<script src="{build.MERMAID_HREF}"></script>\n'
        """<script>
mermaid.initialize({ startOnLoad: false, theme: 'dark' });
mermaid.run({ nodes: document.querySelectorAll('.mermaid') }).catch(function (e) {
  console.error('Mermaid render error:', e);
});
</script>"""
    )
    return body, script
