"""style — CSS styles and Cloudflare middleware assets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from pygments.formatters import HtmlFormatter

from .render import CODE_STYLE

STYLE_HREF = "/style.css"

BASE_CSS = """
:root {
  color-scheme: dark;
  --bg: #1b1d21;
  --side-bg: #15171a;
  --side-hover: #242830;
  --card: #22252a;
  --btn: #2b2f35;
  --btn-hover: #353a42;
  --fg: #dfe1e4;
  --mute: #9aa0a8;
  --faint: #878d95;
  --line: #353941;
  --line-soft: #282c32;
  --accent: #7ba3cc;
  --accent-soft: #26313d;
  --hit: #3a3424;
  --draft: #d9a86c;
  --draft-bg: #3a2f1f;
  --open: #7fc79a;
  --open-bg: #1f3329;
  --r-sm: .45rem;
  --font: ui-sans-serif, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, "Noto Sans Mono", monospace;
  --side: 300px;
}

* { box-sizing: border-box; }
body {
  margin: 0; display: flex; min-height: 100vh;
  background: var(--bg); color: var(--fg);
  font: 15px/1.8 var(--font);
  -webkit-font-smoothing: antialiased; -webkit-text-size-adjust: 100%;
}
a { color: inherit; text-decoration: none; }
/* キーボードで辿ったときだけ枠を出す。.hpath などは all: unset で既定の枠が消えている */
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
#list :focus-visible { outline-offset: -2px; }
.meta { color: var(--faint); font-size: .74rem; }
.empty { color: var(--faint); font-size: .85rem; padding: 3rem 1rem; text-align: center; }

/* ---------- sidebar ---------- */
/* ヘッダは固定枠として外に出し、sticky を使うのは一覧の中のグループ見出しだけにする */
#side {
  flex: 0 0 var(--side); width: var(--side);
  height: 100vh; position: sticky; top: 0;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--line); background: var(--side-bg);
}
#side-head { flex: none; padding: 1rem .9rem .75rem; border-bottom: 1px solid var(--line); }
#side-head h1 { margin: 0 0 .6rem; font: 700 1rem/1.2 var(--font); letter-spacing: .06em; }
#side-head h1 a:hover { color: var(--accent); }
#list { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: .3rem 0 2rem; }

.crumb {
  display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .25rem;
  font: 400 .78rem/1.7 var(--mono); color: var(--mute);
}
.crumb a:hover { color: var(--accent); }
.crumb .sep { color: var(--faint); }
.crumb span:not(.sep) { color: var(--fg); }

.dhead {
  position: sticky; top: 0; z-index: 5; margin: 0;
  padding: 1rem .9rem .5rem; background: var(--side-bg);
  font: 700 .68rem/1.2 var(--font); letter-spacing: .12em; text-transform: uppercase;
  color: var(--accent);
  border-bottom: 1px solid var(--line);
}
/* 行が詰まると目が滑るので、GitHub のツリー同様 1 行 36px 前後を確保する */
.item {
  display: flex; align-items: center; gap: .55rem; min-height: 36px;
  padding: .45rem .9rem;
  font: 400 .84rem/1.6 var(--mono); color: var(--mute);
}
.item:hover { background: var(--side-hover); color: var(--fg); }
.item.on { background: var(--accent-soft); }
.item.on .t { color: var(--accent); }
.item .t { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item .m { flex: none; color: var(--faint); font-size: .72rem; font-variant-numeric: tabular-nums; }
/* ディレクトリとファイルを記号で分ける（アイコン画像を足すと読み込みが増える） */
.item::before { content: ""; flex: none; width: 15px; height: 12px; }
/* ディレクトリは太字＋アクセント色、ファイルは通常色。字形だけでなく色でも段を分ける */
.item.dir { color: var(--fg); font-weight: 600; }
.item.dir .m { color: var(--mute); }
.item.dir:hover { color: #fff; }
/* フォルダ形はグリフだと小さく潰れるので、タブ付きの矩形を CSS で描く */
.item.dir::before,
#list > .item:not(.dir):not(.file)::before {
  background: var(--accent); border-radius: 2px;
  clip-path: polygon(0 6%, 40% 6%, 50% 24%, 100% 24%, 100% 100%, 0 100%);
}
/* ファイルは角を折った紙。フォルダより弱い色にして視線がフォルダに行くようにする */
.item.file::before {
  width: 12px; height: 14px; background: var(--faint); opacity: .55; border-radius: 1px;
  clip-path: polygon(0 0, 65% 0, 100% 28%, 100% 100%, 0 100%);
}
.item.file:hover::before, .item.file.on::before { opacity: 1; }
.item.file.on::before { background: var(--accent); }
/* トップページのリポ一覧は kind クラスを持たないので、同じ扱いに寄せる */
#list > .item:not(.dir):not(.file) { color: var(--fg); font-weight: 600; }

/* ---------- content ---------- */
#main { flex: 1; min-width: 0; padding: 1.3rem 1.6rem 6rem; }
/* 広い画面で中身が端まで伸びないよう、種類ごとの最大幅で止めて中央に寄せる。余りは左右の余白になる */
.wrap { margin: 0 auto; }
.wrap.w-md { max-width: 900px; }
.wrap.w-issue { max-width: 1000px; }
.wrap.w-code { max-width: 1280px; }
#back { display: none; }
/* 本文側のパンくずはスマホだけで使う（PC は左の見出しにある） */
.mcrumb { display: none; }
.readme-head {
  margin: 0 0 1rem; padding: 0 0 .6rem; border-bottom: 1px solid var(--line);
  font: 600 .85rem var(--mono);
}
.readme-head a { color: var(--fg); }
.readme-head a:hover { color: var(--accent); }
.head {
  display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap;
  padding-bottom: .7rem; margin-bottom: 1rem; border-bottom: 1px solid var(--line);
}
/* 長いファイルを下まで読んでも、名前とコピーの釦が手の届く所に残るようにする */
.head[data-path] {
  position: sticky; top: 0; z-index: 4; background: var(--bg);
  padding-top: .6rem; margin-top: -.6rem;
}
.head h2 { margin: 0; font: 650 1.05rem/1.4 var(--mono); }
.head h2 .hpath {
  all: unset; cursor: pointer; border-bottom: 1px dashed var(--line);
}
.head h2 .hpath:hover { color: var(--accent); border-bottom-color: var(--accent); }
.head h2 .hpath:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.head .hbtns { margin-left: auto; display: flex; gap: .4rem; }
.head .hbtns:empty { display: none; }
.head .hact {
  cursor: pointer;
  padding: .25rem .6rem; border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--btn); color: var(--mute); font: 500 .72rem var(--mono);
}
.head .hact[hidden] { display: none; }
.head .hact:hover { background: var(--btn-hover); color: var(--fg); }
.head .flash { color: var(--accent); font: 500 .72rem var(--mono); }

/* 同じディレクトリの前後のファイル */
.pager {
  display: flex; justify-content: space-between; gap: 1rem;
  margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
  font: 500 .8rem var(--mono);
}
.pager a {
  min-width: 0; max-width: 48%; padding: .45rem .8rem;
  border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--btn); color: var(--mute);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pager a:hover { background: var(--btn-hover); color: var(--fg); }
.pager .next { margin-left: auto; }

/* ---------- code ---------- */
.hl {
  background: transparent;
  border: none;
  margin: 1em 0;
  padding: 0;
}

/* 行の高さ・文字サイズは GitHub の blob 表示に合わせる（12px / 20px） */
.hl pre, pre.plain, .markdown-body pre {
  border: 1px solid var(--line);
  border-radius: var(--r-sm); background: var(--card);
  margin: 0; padding: .8rem 1rem;
  font: 12px/20px var(--mono);
  white-space: pre-wrap; overflow-wrap: anywhere;
}
/* 折り返した続きの行を行番号ぶん字下げして、行の始まりを見分けられるようにする */
.hl pre > span[id^="ln-"] {
  display: block; padding-left: 4rem; text-indent: -4rem;
  scroll-margin-top: 5rem;  /* 固定したヘッダの下に隠れないように */
}
/* #ln-N で開いた行、押した行に色を付ける。JS があるときは .hit だけを使う
   （history.replaceState では :target が付け替わらない） */
body:not(.lnjs) .hl pre > span[id^="ln-"]:target,
.hl pre > span.hit {
  margin: 0 -1rem; padding-left: 5rem;
  background: var(--hit); box-shadow: inset 3px 0 0 var(--draft);
}
/* pygments の github-dark は行番号 span ごとに黒を塗る。本文背景から浮くので消す */
.hl span.linenos {
  background: none; color: var(--faint); user-select: none; cursor: pointer;
  display: inline-block; width: 3.2rem; text-align: right;
  padding: 0 .8rem 0 0;
}
.hl span.linenos:hover { color: var(--accent); }
/* Wrap: off。行は折り返さず、箱の中を横に送る */
.nowrap .hl pre, .nowrap pre.plain {
  white-space: pre; overflow-wrap: normal; overflow-x: auto;
}
.nowrap .hl pre > span[id^="ln-"] { width: max-content; min-width: 100%; }
.nowrap .hl pre > span.hit { min-width: calc(100% + 2rem); }

/* ---------- markdown & mermaid ---------- */
.markdown-body {
  font-family: var(--font);
  line-height: 1.7;
  color: var(--fg);
}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {
  margin-top: 1.6em;
  margin-bottom: 0.6em;
  font-weight: 650;
  line-height: 1.3;
}
.markdown-body h1 {
  font-size: 1.6rem;
  padding-bottom: 0.4em;
  border-bottom: 1px solid var(--line);
}
.markdown-body h2 {
  font-size: 1.3rem;
  padding-bottom: 0.3em;
  border-bottom: 1px solid var(--line-soft);
}
.markdown-body h3 { font-size: 1.1rem; }
/* 目次から飛んだ見出しが、固定したファイル名のヘッダの下に隠れないように */
.markdown-body :is(h1, h2, h3, h4) { scroll-margin-top: 4.5rem; }
.markdown-body .toc {
  margin: 0 0 1.4rem; padding: .45rem .9rem;
  border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--card);
}
.markdown-body .toc > summary {
  cursor: pointer; color: var(--mute); font: 600 .78rem/1.8 var(--mono);
  letter-spacing: .04em;
}
.markdown-body .toc > summary:hover { color: var(--fg); }
.markdown-body .toc ul { list-style: none; margin: .3rem 0 .2rem; padding: 0; }
.markdown-body .toc li { margin: 0; font-size: .88rem; line-height: 1.9; }
.markdown-body .toc li.l1 { padding-left: 1.1rem; }
.markdown-body .toc li.l2 { padding-left: 2.2rem; font-size: .84rem; }
.markdown-body .toc a { color: var(--mute); text-decoration: none; }
.markdown-body .toc a:hover { color: var(--accent); }
.markdown-body a { color: var(--accent); text-decoration: underline; }
.markdown-body p { margin: 0.8em 0; }
.markdown-body blockquote {
  margin: 1em 0;
  padding: 0.5em 1em;
  color: var(--mute);
  background: var(--card);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
}
.markdown-body blockquote p { margin: 0.4em 0; }
/* 表は本文の幅を超えると、ページごと横にずれる。表の箱だけを横スクロールさせる。
   block にすると中身の幅に縮むので、max-content で中身に合わせ、本文の幅で止める */
.markdown-body table {
  display: block;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 0.85rem;
  font-family: var(--mono);
}
.markdown-body th, .markdown-body td {
  border: 1px solid var(--line);
  padding: 0.5rem 0.8rem;
  text-align: left;
}
.markdown-body th {
  background: var(--btn);
  font-weight: 600;
  color: var(--fg);
}
.markdown-body tr:nth-child(even) { background: rgba(255, 255, 255, 0.02); }
.markdown-body ul, .markdown-body ol { padding-left: 1.6em; margin: 0.8em 0; }
.markdown-body li { margin: 0.3em 0; }
.markdown-body code:not(pre code) {
  background: var(--card);
  color: var(--fg);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: var(--mono);
  font-size: 0.85em;
  border: 1px solid var(--line-soft);
}
.markdown-body pre code {
  background: transparent;
  padding: 0;
  border: none;
  font-size: inherit;
}
.markdown-body hr {
  height: 1px;
  background: var(--line);
  border: 0;
  margin: 1.8em 0;
}
/* flex にすると mermaid が文字の位置を測り違え、軸ラベルが下で切れ、軸の題が目盛りに重なる */
.mermaid {
  display: block;
  text-align: center;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 1.2rem;
  margin: 1.5em 0;
  overflow-x: auto;
}
/* mermaid は図の箱の中に一時の div を作って文字を測る。狭い画面ではその幅で測って
   軸の題が目盛りに重なるので、描いた後の大きさ（既定の 700px）で測らせる */
.mermaid > div[id^="d"] { width: 700px; }
.imgfile {
  display: block;
  max-width: 100%;
  height: auto;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 4px;
}
.markdown-body img {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}

/* ---------- issues ---------- */
/* アカウント行はフォルダ形ではなく丸で示す */
#list > .item.acct:not(.dir):not(.file)::before {
  width: 10px; height: 10px; margin: 0 2.5px; border-radius: 50%;
  background: var(--accent); clip-path: none;
}
.head .hissue {
  color: var(--accent); font: 500 .74rem var(--mono);
  border-bottom: 1px dashed var(--accent);
}
.head .hissue:hover { color: var(--fg); border-bottom-color: var(--fg); }
.head .count { margin-left: auto; }

/* サイドバーのアカウント切り替え */
.tabs { display: flex; gap: .4rem; margin-top: .7rem; }
.tabs a {
  flex: 1; text-align: center; padding: .3rem .5rem;
  border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--btn); color: var(--mute); font: 500 .78rem var(--mono);
}
.tabs a:hover { background: var(--btn-hover); color: var(--fg); }
.tabs a.on { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }
/* 選んだリポの下に並ぶ Issue。フォルダ形の記号は付けず、字下げで階層を示す */
.item.iss { min-height: 32px; padding-left: 2rem; font-size: .8rem; }
.item.iss::before { display: none; }
.item.iss .n { flex: none; color: var(--faint); }
.item.iss.on .n { color: var(--accent); }
.fail { margin: 0 0 .8rem; color: #d98b8b; font: .8rem var(--mono); }

.issue {
  position: relative; padding: .8rem .9rem; border-bottom: 1px solid var(--line-soft);
}
.issue:first-child { border-top: 1px solid var(--line-soft); }
.issue:hover { background: var(--side-hover); }
.i-top { display: flex; align-items: baseline; gap: .8rem; }
.i-title { flex: 1; min-width: 0; font-weight: 600; overflow-wrap: anywhere; }
/* 行全体を押せるようにする。入れ子のリンクは前面に出して別に押せるようにする */
.i-title::after { content: ""; position: absolute; inset: 0; }
.i-title:hover { color: var(--accent); }
.i-sub { margin-top: .15rem; color: var(--faint); font: .76rem/1.7 var(--mono); overflow-wrap: anywhere; }
.i-sub .wait { position: relative; z-index: 1; color: var(--accent); }
.i-sub .wait:hover { text-decoration: underline; }
.badge {
  flex: none; padding: .05rem .55rem; border-radius: 1rem;
  border: 1px solid currentColor; font: 600 .7rem/1.6 var(--mono);
}
.badge.draft { color: var(--draft); background: var(--draft-bg); }
.badge.open { color: var(--open); background: var(--open-bg); }

/* ---------- issue page ---------- */
.ihead { padding-bottom: .9rem; margin-bottom: 1.2rem; border-bottom: 1px solid var(--line); }
.ititle { margin: 0 0 .6rem; font: 650 1.45rem/1.35 var(--font); overflow-wrap: anywhere; }
.ititle .inum { color: var(--faint); font-weight: 400; }
.isub {
  display: flex; flex-wrap: wrap; align-items: center; gap: .4rem .7rem;
  color: var(--faint); font: .78rem/1.7 var(--mono);
}
.isub .wait { color: var(--accent); }
.isub .wait:hover { text-decoration: underline; }
/* mermaid が svg の中で `g.label` を使うので、素の .label にすると図の軸ラベルが崩れる */
.ilabel {
  padding: 0 .55rem; border: 1px solid var(--line); border-radius: 1rem;
  background: var(--card); color: var(--mute); font: 500 .72rem/1.6 var(--mono);
}
.ilinks { margin: -.2rem 0 1.2rem; color: var(--mute); font: .78rem/1.9 var(--mono); }
.ilinks .k { display: inline-block; min-width: 6.5em; color: var(--faint); }
.ilinks a { color: var(--accent); margin-right: .8rem; overflow-wrap: anywhere; }
.ilinks a:hover { text-decoration: underline; }
.ilinks span:not(.k) { margin-right: .8rem; overflow-wrap: anywhere; }

/* カードの間に縦の線を通す。カードは不透明なので、線は隙間にだけ見える */
.thread { position: relative; display: flex; flex-direction: column; gap: 1.1rem; }
.thread::before {
  content: ""; position: absolute; left: 1.4rem; top: 0; bottom: 0;
  width: 2px; background: var(--line);
}
.card {
  position: relative; min-width: 0; overflow: hidden;
  border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg);
}
.chead {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: .15rem .45rem;
  padding: .5rem .9rem; background: var(--card); border-bottom: 1px solid var(--line);
  color: var(--faint); font: .78rem/1.6 var(--mono);
}
.chead .who { color: var(--fg); font-weight: 650; }
.cbody { padding: .3rem 1.1rem .5rem; overflow-x: auto; overflow-wrap: anywhere; }
.cbody .markdown-body > :first-child { margin-top: .6em; }
.cbody .markdown-body > :last-child { margin-bottom: .6em; }
.cbody .markdown-body h1 { font-size: 1.35rem; }
.cbody .markdown-body h2 { font-size: 1.15rem; }
.cbody .markdown-body h3 { font-size: 1.02rem; }
.nobody { margin: .7rem 0; color: var(--faint); font-style: italic; }
.noimg { color: var(--faint); font-family: var(--mono); font-size: .85em; }

/* ---------- mobile ---------- */
@media (max-width: 760px) {
  body { display: block; }
  #side { position: static; display: block; width: auto; height: auto; border-right: 0; }
  #side-head {
    position: sticky; top: 0; z-index: 10; background: var(--side-bg);
    padding-top: calc(.8rem + env(safe-area-inset-top, 0px));
  }
  #list { overflow: visible; }
  /* ページ全体が1つのスクロール文脈になるので、見出しを sticky にするとヘッダと重なる */
  .dhead { position: static; }
  .item { padding: .7rem .8rem; }
  #main { padding: 1rem 1rem 5rem; }
  /* ファイルのページは左の一覧ごと隠れるので、パンくずを本文の先頭に出す */
  .mcrumb { display: flex; margin-bottom: 1.1rem; font-size: .8rem; }
  .head[data-path] { padding-top: calc(.6rem + env(safe-area-inset-top, 0px)); }
  .pager a { padding: .6rem .8rem; }
  body.detail #side { display: none; }
  body:not(.detail):not(.home):not(.readme) #main { display: none; }
  /* README のあるディレクトリは、GitHub と同じく一覧の下に README を出す */
  body.readme #main { border-top: 1px solid var(--line); }
  /* トップは要約を見せたいので、メニュー（#list）より上に main を置く。
     タイトル行は先頭のまま。#side を畳んで3つを同じ並びで order する */
  body.home { display: flex; flex-direction: column; }
  body.home #side { display: contents; }
  /* #side の背景が消えて本文と同じ地に並ぶので、見出しも地の色に揃える */
  body.home #side-head, body.home .dhead { background: var(--bg); }
  body.home #side-head { order: 0; }
  body.home #main { order: 1; padding-bottom: 1rem; }
  body.home #list { order: 2; padding-bottom: 5rem; }
  #back {
    display: inline-flex; align-items: center; gap: .3rem; margin-bottom: .7rem;
    padding: .35rem .7rem; border: 1px solid var(--line); border-radius: var(--r-sm);
    background: var(--btn); color: var(--mute); font: 500 .82rem var(--mono);
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  #back:hover { background: var(--btn-hover); color: var(--fg); }
}
"""

MIDDLEWARE = """export const onRequest = ({ request, next }) => {
  const host = new URL(request.url).hostname;
  if (host === 'pages.dev' || host.endsWith('.pages.dev')) {
    return new Response('not found', { status: 404 });
  }
  return next();
};
"""


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#26313d"/>'
    '<g transform="translate(4 4)" fill="none" stroke="#7ba3cc" stroke-width="2.25"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/></g></svg>\n'
)


def write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_style(out_root: Path, extra_css: str = "") -> str:
    global STYLE_HREF
    defs = HtmlFormatter(style=CODE_STYLE, cssclass="hl").get_style_defs(".hl")
    css = defs + "\n" + BASE_CSS + extra_css
    digest = hashlib.sha256(css.encode()).hexdigest()[:10]
    STYLE_HREF = f"/style.{digest}.css"
    write(out_root / f"style.{digest}.css", css)
    write(out_root / "favicon.svg", FAVICON)
    return STYLE_HREF
