"""render — Syntax highlighting and Markdown/Mermaid rendering."""

from __future__ import annotations

import html
import posixpath
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import markdown
from markdown.extensions import Extension
from markdown.extensions.toc import slugify_unicode
from markdown.postprocessors import Postprocessor
from markdown.treeprocessors import Treeprocessor
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.util import ClassNotFound

MAX_BYTES = 512 * 1024
HIGHLIGHT_MAX_BYTES = 96 * 1024
CODE_STYLE = "github-dark"

# 生成物にコピーして表示する画像。大きすぎるものはコピーしない
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg")
MAX_IMAGE_BYTES = 5 * 1024 * 1024

MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def is_text(data: bytes) -> bool:
    return b"\0" not in data


def is_image(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTS)


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
    # 生成物にコピーした画像のリポ内パス
    images: frozenset[str] = frozenset()

    def _target(self, raw: str) -> str | None:
        """`.md` の位置（`/` 始まりはリポのルート）を基準にしたリポ内パス。リポの外は None。"""
        if raw.startswith("/"):
            target = posixpath.normpath(raw.lstrip("/") or ".")
        else:
            base = posixpath.dirname(self.md_path)
            target = posixpath.normpath(posixpath.join(base, raw))
        if target == ".":
            target = ""
        if target == ".." or target.startswith("../"):
            return None
        return target

    def resolve(self, href: str) -> str | None:
        """リポ内のページを指すリンクならサイト内の絶対パスを返す。外部・アンカーは href のまま、
        ページの無い先は None。"""
        parts = urlsplit(href.strip())
        if parts.scheme or parts.netloc or not parts.path:
            return href
        raw = unquote(parts.path)
        target = self._target(raw)
        if target is None:
            return None
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if not raw.endswith("/") and target in self.files:
            return f"/{self.slug}/{target}.html{frag}"
        if target in self.dirs:
            return f"/{self.slug}/" + (f"{target}/" if target else "") + frag
        return None

    def resolve_image(self, src: str) -> str | None:
        """コピーした画像を指す src ならサイト内の絶対パスを返す。無ければ（リポ外の URL を含む）None。"""
        parts = urlsplit(src.strip())
        if parts.scheme or parts.netloc or not parts.path:
            return None
        target = self._target(unquote(parts.path))
        if target is None or target not in self.images:
            return None
        return f"/{self.slug}/{quote(target)}"


@dataclass(frozen=True)
class GitHubRepo:
    slug: str
    account: str | None
    # 生成したのはこのブランチの HEAD。他の ref を指す URL は中身が違いうるので向けない
    branch: str | None
    files: frozenset[str]
    dirs: frozenset[str]


@dataclass(frozen=True)
class GitHubLinks:
    """GitHub の URL のうち、生成したページに対応するものをサイト内へ向けるための材料。

    repos は `owner/repo`（小文字）から走査対象のリポへ。issues は (`owner/repo`, 番号) から
    (アカウント, Issue のページ) へ。
    """

    repos: dict[str, GitHubRepo]
    issues: dict[tuple[str, str], tuple[str, str]]

    def resolve(self, href: str, account: str | None) -> str | None:
        """対応するページがあればサイト内の絶対パスを、無ければ None を返す。

        Issue へはアカウントが同じときだけ向ける。
        """
        parts = urlsplit(href.strip())
        if parts.scheme.lower() not in ("http", "https"):
            return None
        if (parts.hostname or "") not in ("github.com", "www.github.com"):
            return None
        segs = [unquote(s) for s in parts.path.split("/") if s]
        if len(segs) < 2:
            return None
        key = f"{segs[0]}/{segs[1].removesuffix('.git')}".lower()
        repo = self.repos.get(key)
        if repo is None:
            return None
        rest = segs[2:]
        if not rest:
            return f"/{repo.slug}/"
        if rest[0] == "issues" and len(rest) == 2:
            hit = self.issues.get((key, rest[1]))
            if hit is not None and account is not None and hit[0] == account:
                return hit[1]
            return None
        if rest[0] not in ("blob", "tree") or repo.branch is None:
            return None
        ref = repo.branch.split("/")
        if rest[1 : 1 + len(ref)] != ref:
            return None
        target = "/".join(rest[1 + len(ref) :])
        frag = f"#{parts.fragment}" if parts.fragment else ""
        if rest[0] == "blob" and target in repo.files:
            return f"/{repo.slug}/{target}.html{frag}"
        if target in repo.dirs:
            return f"/{repo.slug}/" + (f"{target}/" if target else "") + frag
        return None


class _ResolveLinks(Treeprocessor):
    """生成したページに対応するリンクをそのページへ向ける。

    GitHub の URL は github で引く。links があれば、リポ内を指す相対リンクも解決し、
    ページの無い先はリンクでない文字にする。
    """

    def __init__(
        self,
        md,
        links: LinkContext | None,
        github: GitHubLinks | None,
        account: str | None,
    ):
        super().__init__(md)
        self.links = links
        self.github = github
        self.account = account

    def run(self, root):
        for el in root.iter("a"):
            href = el.get("href")
            if href is None:
                continue
            if self.github is not None:
                inner = self.github.resolve(href, self.account)
                if inner is not None:
                    el.set("href", inner)
                    continue
            if self.links is None:
                continue
            new = self.links.resolve(href)
            if new is None:
                el.attrib.clear()
                el.tag = "span"
            else:
                el.set("href", new)


def _noimg(alt: str | None) -> str:
    return f'<span class="noimg">[{html.escape(alt or "image")}]</span>'


class _ResolveImages(Treeprocessor):
    """`![]()` をコピーした画像へ向ける。向け先の無い画像は `[alt]` の文字にする。"""

    def __init__(self, md, links: LinkContext):
        super().__init__(md)
        self.links = links

    def run(self, root):
        for el in root.iter("img"):
            new = self.links.resolve_image(el.get("src", ""))
            if new is None:
                alt = el.get("alt") or "image"
                el.attrib.clear()
                el.tag = "span"
                el.set("class", "noimg")
                el.text = f"[{alt}]"
            else:
                el.set("src", new)


_IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
_ATTR = re.compile(r"""([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""")


class _ResolveRawImages(Postprocessor):
    """生の HTML の `<img>` を `![]()` と同じ規則でコピーした画像へ向ける。

    生の HTML は htmlStash に退避されていて Treeprocessor から見えない。描き終えた HTML 全体を
    書き換えると `![]()` の解決済みの src をもう一度解決してしまうので、退避した塊だけを書き換える。
    """

    def __init__(self, md, links: LinkContext):
        super().__init__(md)
        self.links = links
        # toc が見出しを描くときにも後処理が走る。書き換えた塊をもう一度解決しない
        self._done: set[int] = set()

    def run(self, text):
        blocks = self.md.htmlStash.rawHtmlBlocks
        for i, block in enumerate(blocks):
            if i not in self._done:
                self._done.add(i)
                blocks[i] = _IMG_TAG.sub(self._img, block)
        return text

    def _img(self, m: re.Match) -> str:
        attrs = []
        src = alt = None
        for name, dq, sq, bare in _ATTR.findall(m.group(0)[len("<img") : -1].rstrip("/")):
            value = html.unescape(next((v for v in (dq, sq, bare) if v), ""))
            if name.lower() == "src":
                src = value
            else:
                if name.lower() == "alt":
                    alt = value
                attrs.append((name, value))
        new = self.links.resolve_image(src) if src is not None else None
        if new is None:
            return _noimg(alt)
        rest = "".join(f' {n}="{html.escape(v, quote=True)}"' for n, v in attrs)
        return f'<img src="{html.escape(new, quote=True)}"{rest}>'


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
    github: GitHubLinks | None = None,
    account: str | None = None,
) -> tuple[str, str]:
    """safe は信頼できない入力用（生の HTML を実行せず、画像と GitHub へのリンクを出さない）。

    refs は safe のときだけ使い、`#N` から飛び先への対応を渡す。
    links は safe でないときだけ使い、リポ内への相対リンクの解決に使う。
    github を渡すと、GitHub の URL のうち生成したページに対応するものは、safe でもそのページへ向ける。
    account は読んでいる文書のアカウントで、Issue へ向けるかの判定に使う。
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
    resolve = links if not safe else None
    if resolve is not None or github is not None:
        # _Sanitize（5）が GitHub へのリンクを文字にする前に書き換える
        md.treeprocessors.register(
            _ResolveLinks(md, resolve, github, account), "resolve_links", 6
        )
    if resolve is not None:
        md.treeprocessors.register(_ResolveImages(md, resolve), "resolve_images", 6)
        # raw_html（30）が退避した塊を戻す前に書き換える
        md.postprocessors.register(_ResolveRawImages(md, resolve), "resolve_raw_images", 35)
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
