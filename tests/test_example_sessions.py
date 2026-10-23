"""例の拡張 examples/plugins/sessions.py: ccreel の一覧と本文から、セッションのページを書く。"""

from __future__ import annotations

import json
import posixpath
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT, git

EXAMPLE = ROOT / "examples" / "plugins" / "sessions.py"

# 偽の ccreel。`list` は $FAKE_CCREEL_DIR/list-<config dir の名前>.jsonl（無ければ list.jsonl）を、
# `show <id>` は <id>.jsonl を返す。受けた引数を calls.log に残す
FAKE_CCREEL = """#!/usr/bin/env python3
import os, sys
d = os.environ["FAKE_CCREEL_DIR"]
with open(os.path.join(d, "calls.log"), "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
config = os.path.basename(sys.argv[sys.argv.index("--config-dir") + 1])
name = sys.argv[2]
if sys.argv[1] == "list":
    name = "list-" + config if os.path.exists(os.path.join(d, "list-" + config + ".jsonl")) else "list"
path = os.path.join(d, name + ".jsonl")
if not os.path.exists(path):
    sys.stderr.write("no session\\n")
    sys.exit(1)
sys.stdout.write(open(path).read())
"""

# alpha の Issue を1本返す取り込み元。設定の隣に `closed` というファイルがあれば消化済みとして返さない
SOURCE = '''
from pathlib import Path

from codeview.issues import Issue


def issues(ctx, account, repos):
    if (Path(__file__).parent / "closed").exists():
        return []
    return [
        Issue(
            account=account.name, repo=repo.path.name, slug=repo.slug, ref="01",
            title="first issue", kind="", state="Open", updated=1,
        )
        for repo in repos
        if repo.path.name == "alpha"
    ]
'''

SESSIONS = [
    {
        "id": "aaaa1111-0000-0000-0000-000000000000",
        "repo": "alpha",
        "branch": "claude/1-first",
        "issue": "1",
        "title": "最初の作業",
        "first_prompt": "main.py を直したい",
        "prompts": 3,
        "started": "2026-03-01T00:00:00Z",
        "updated": "2026-03-01T01:00:00Z",
    },
    {
        "id": "bbbb2222-0000-0000-0000-000000000000",
        "repo": "beta",
        "title": "別の相談",
        "first_prompt": "beta について",
        "prompts": 2,
        "started": "2026-02-01T00:00:00Z",
        "updated": "2026-02-01T00:30:00Z",
    },
]

TURNS = [
    {
        "turn": 1,
        "time": "2026-03-01T00:00:00Z",
        "prompt": "main.py を直したい\n2行目",
        "messages": [{"kind": "text", "text": "**直します** <script>alert(1)</script>"}],
    },
    {"turn": 2, "time": "2026-03-01T00:10:00Z", "prompt": "続けて", "messages": []},
]


def _first(name: str = "id") -> str:
    return SESSIONS[0][name]


@pytest.fixture
def ccreel(site, tmp_path: Path) -> Path:
    d = tmp_path / "ccreel"
    d.mkdir()
    (d / "list.jsonl").write_text("".join(json.dumps(s) + "\n" for s in SESSIONS))
    # beta のセッションは show に失敗させる（本文のファイルを置かない）
    (d / f"{_first()}.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TURNS))
    exe = tmp_path / "bin" / "ccreel"
    exe.write_text(FAKE_CCREEL)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    site.env["FAKE_CCREEL_DIR"] = str(d)
    return d


def _use_sessions(site, extra: str = "") -> None:
    """例の拡張と Issue の取り込み元を設定の隣に置き、alpha を持つアカウントの取り込み元にする。"""
    shutil.copy(EXAMPLE, site.config.parent / "sessions.py")
    (site.config.parent / "issuesrc.py").write_text(SOURCE)
    site.write_config(
        site.config.read_text().replace('groups = ["own"]\n', 'groups = ["own"]\nissues = "issuesrc"\n')
        + '\n[plugins]\nmodules = ["issuesrc", "sessions"]\n'
        + extra
    )


def _page(public: Path, session: dict) -> str:
    return (public / "sessions" / f"{session['id']}.html").read_text()


def test_list_and_session_pages(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    listing = (public / "sessions" / "index.html").read_text()
    assert "最初の作業" in listing and "別の相談" in listing
    assert 'data-repo="alpha"' in listing and 'data-issue="1"' in listing
    # 新しい順
    assert listing.index("最初の作業") < listing.index("別の相談")
    page = _page(public, SESSIONS[0])
    assert "main.py を直したい\n2行目" in page
    assert "続けて" in page
    assert f"ccreel resume {_first()}" in page
    calls = (ccreel / "calls.log").read_text().splitlines()
    assert f"list --json --limit 0 --since 30d --config-dir {site.home}/.claude" in calls
    assert any(c.startswith(f"show {_first()} --json ") for c in calls)


def test_reply_markdown_is_safe(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    page = _page(public, SESSIONS[0])
    assert "<strong>直します</strong>" in page
    # 応答の生の HTML は実行させない
    assert "<script>alert(1)</script>" not in page


def test_links_to_issue_and_repo(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    page = _page(public, SESSIONS[0])
    # Issue 01 は ccreel では 1 と出る。先頭の 0 を無視して結ぶ
    assert 'href="../issues/me/alpha/01.html"' in page
    assert 'href="../alpha/index.html"' in page
    # Issue の無いセッションには Issue のリンクが出ない
    other = _page(public, SESSIONS[1])
    assert "issues/" not in other.split('class="isub"')[1].split("</div>")[0]
    assert 'href="../beta/index.html"' in other


def test_unlinked_when_issue_or_repo_is_missing(site, ccreel):
    # 一覧に無い Issue 番号は文字だけ。走査対象に無いリポはリンクにしない
    rows = [dict(SESSIONS[0], issue="9"), dict(SESSIONS[1], repo="elsewhere", issue="2")]
    (ccreel / "list.jsonl").write_text("".join(json.dumps(s) + "\n" for s in rows))
    _use_sessions(site)
    public, _ = site.build()
    page = _page(public, SESSIONS[0])
    assert "<span>#9</span>" in page and "issues/me/alpha/09.html" not in page
    other = _page(public, SESSIONS[1])
    assert "<span>#2</span>" in other and "../elsewhere/" not in other and 'class="k">Repo<' not in other


def test_unreadable_session_still_gets_a_page(site, ccreel):
    _use_sessions(site)
    public, proc = site.build()
    # 読めなかったセッションもページは作り、一覧のリンクを切らさない
    assert "Could not read this session" in _page(public, SESSIONS[1])
    assert "Could not read this session" not in _page(public, SESSIONS[0])
    assert f"ccreel show {SESSIONS[1]['id']} failed" in proc.stderr


def test_top_menu_links_sessions_without_titles(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    top = (public / "index.html").read_text()
    assert 'href="sessions/index.html"' in top
    assert '<span class="m">2</span>' in top
    assert "最初の作業" not in top and "別の相談" not in top


def test_passes_config_dir_and_period(site, ccreel):
    _use_sessions(site, '\n[plugins.sessions]\nconfig_dirs = ["~/.claude-x"]\ndays = 7\n')
    public, _ = site.build()
    calls = (ccreel / "calls.log").read_text().splitlines()
    first = next(c for c in calls if c.startswith("list "))
    assert "--since 7d" in first
    assert f"--config-dir {site.home}/.claude-x" in first
    # config dir が1つなら、どこのセッションかは出さない
    assert ".claude-x" not in (public / "sessions" / "index.html").read_text()


def test_merges_config_dirs(site, ccreel):
    work = {
        "id": "cccc3333-0000-0000-0000-000000000000",
        "repo": "gamma",
        "title": "仕事の相談",
        "first_prompt": "gamma の件",
        "prompts": 4,
        "started": "2026-02-15T00:00:00Z",
        "updated": "2026-02-15T00:30:00Z",
    }
    (ccreel / "list-.claude-work.jsonl").write_text(json.dumps(work) + "\n")
    _use_sessions(site, '\n[plugins.sessions]\nconfig_dirs = ["~/.claude", "~/.claude-work"]\n')
    public, _ = site.build()
    listing = (public / "sessions" / "index.html").read_text()
    # 更新の新しい順に混ぜる
    order = [listing.index(t) for t in ("最初の作業", "仕事の相談", "別の相談")]
    assert order == sorted(order)
    assert ".claude-work" in listing
    calls = (ccreel / "calls.log").read_text().splitlines()
    assert f"show {work['id']} --json --max-chars 20000 --max-total 0 --config-dir {site.home}/.claude-work" in calls
    assert (public / "sessions" / f"{work['id']}.html").is_file()


def test_build_survives_one_failing_config_dir(site, ccreel):
    _use_sessions(site, '\n[plugins.sessions]\nconfig_dirs = ["~/.claude", "~/.claude-broken"]\n')
    (ccreel / "list-.claude-broken.jsonl").write_text("not json\n")
    public, proc = site.build()
    assert "最初の作業" in (public / "sessions" / "index.html").read_text()
    assert "warning: sessions: ccreel list failed for ~/.claude-broken" in proc.stderr


def _assert_build_stops(site, *reasons: str) -> None:
    _, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr
    for reason in reasons:
        assert reason in proc.stderr
    assert not (Path(site.env["CODEVIEW_OUT"]) / "public").exists()


def test_build_stops_without_ccreel(site, ccreel):
    _use_sessions(site, '\n[plugins.sessions]\nccreel = "/nonexistent/ccreel"\n')
    _assert_build_stops(site, "~/.claude", "/nonexistent/ccreel")


def test_build_stops_when_every_list_fails(site, ccreel):
    _use_sessions(site, '\n[plugins.sessions]\nconfig_dirs = ["~/.claude", "~/.claude-broken"]\n')
    (ccreel / "list.jsonl").unlink()
    (ccreel / "list-.claude-broken.jsonl").write_text("not json\n")
    # config dir ごとの理由が出る。1つ目は偽の ccreel の標準エラー、2つ目は JSON の誤り
    _assert_build_stops(site, "~/.claude: no session", "~/.claude-broken: ")


@pytest.mark.parametrize("field", ["id", "repo", "title", "prompts", "started", "updated"])
def test_build_stops_when_a_list_row_lacks_a_field(site, ccreel, field):
    row = {k: v for k, v in SESSIONS[0].items() if k != field}
    (ccreel / "list.jsonl").write_text(json.dumps(row) + "\n")
    _use_sessions(site)
    _assert_build_stops(site, "~/.claude", f"'{field}'")


def test_build_with_empty_list_is_not_an_error(site, ccreel):
    (ccreel / "list.jsonl").write_text("")
    _use_sessions(site)
    public, _ = site.build()
    assert (public / "index.html").is_file()
    assert not (public / "sessions").exists()


def test_publish_if_changed_does_not_push_when_list_fails(site, ccreel, tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(site.config.parent, "remote", "add", "origin", str(remote))
    _use_sessions(site, '\n[plugins.sessions]\nccreel = "/nonexistent/ccreel"\n')
    proc = site.run("-m", "codeview", "publish", "--if-changed", check=False)
    assert proc.returncode != 0
    assert "/nonexistent/ccreel" in proc.stderr
    assert git(remote, "branch", "--list", "deploy") == ""


@pytest.mark.parametrize(
    "extra, message",
    [
        ("everyhours = 3", "unknown key 'everyhours'"),
        ('days = "7"', "'days' must be a positive integer"),
        ("every_hours = 0", "'every_hours' must be a positive integer"),
        ("config_dirs = []", "'config_dirs' must be a non-empty list of strings"),
        ('ccreel = ""', "'ccreel' must be a non-empty string"),
    ],
)
def test_rejects_bad_options(site, ccreel, extra, message):
    _use_sessions(site, f"\n[plugins.sessions]\n{extra}\n")
    _, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr and message in proc.stderr


def test_fingerprint_moves_only_across_windows(site, ccreel):
    _use_sessions(site)

    def at(newest: str, older: str = "2026-02-01T00:30:00Z") -> str:
        rows = [dict(SESSIONS[0], updated=newest), dict(SESSIONS[1], updated=older)]
        (ccreel / "list.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        return site.fingerprint()

    # 既定の every_hours は 3。最新の更新が同じ枠（00:00〜03:00）の中なら変わらない
    assert at("2026-03-01T00:10:00Z") == at("2026-03-01T02:50:00Z")
    assert at("2026-03-01T02:50:00Z") != at("2026-03-01T03:10:00Z")
    # 古い方のセッションが動いても、最新を超えなければ変わらない。超えれば最新として拾う
    assert at("2026-03-01T01:00:00Z") == at("2026-03-01T01:00:00Z", older="2026-02-20T00:00:00Z")
    assert at("2026-03-01T01:00:00Z") != at("2026-03-01T01:00:00Z", older="2026-03-05T00:00:00Z")


def test_fingerprint_follows_every_hours(site, ccreel):
    _use_sessions(site, "\n[plugins.sessions]\nevery_hours = 24\n")
    (ccreel / "list.jsonl").write_text(json.dumps(dict(SESSIONS[0], updated="2026-03-01T03:10:00Z")) + "\n")
    inside = site.fingerprint()
    (ccreel / "list.jsonl").write_text(json.dumps(dict(SESSIONS[0], updated="2026-03-01T23:50:00Z")) + "\n")
    assert site.fingerprint() == inside
    (ccreel / "list.jsonl").write_text(json.dumps(dict(SESSIONS[0], updated="2026-03-02T00:10:00Z")) + "\n")
    assert site.fingerprint() != inside


def _shows(ccreel: Path) -> list[str]:
    log = ccreel / "calls.log"
    lines = log.read_text().splitlines() if log.exists() else []
    log.unlink(missing_ok=True)
    return [line.split()[1] for line in lines if line.startswith("show ")]


def _cache(site) -> Path:
    return Path(site.env["XDG_CACHE_HOME"]) / "codeview" / "sessions"


def test_second_build_reuses_unchanged_pages(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    first = _page(public, SESSIONS[0])
    assert set(_shows(ccreel)) == {SESSIONS[0]["id"], SESSIONS[1]["id"]}
    public, proc = site.build()
    # 読めた方は読み直さない。読めなかった方は使い回さず、毎回読み直す
    assert _shows(ccreel) == [SESSIONS[1]["id"]]
    assert _page(public, SESSIONS[0]) == first
    assert "sessions: 2 pages (1 rebuilt)" in proc.stderr


def test_updated_session_is_rebuilt(site, ccreel):
    _use_sessions(site)
    site.build()
    _shows(ccreel)
    rows = [dict(s) for s in SESSIONS]
    rows[0]["updated"] = "2026-03-02T00:00:00Z"
    turns = TURNS + [{"turn": 3, "time": "2026-03-02T00:00:00Z", "prompt": "追記した発言", "messages": []}]
    (ccreel / "list.jsonl").write_text("".join(json.dumps(s) + "\n" for s in rows))
    (ccreel / f"{_first()}.jsonl").write_text("".join(json.dumps(t) + "\n" for t in turns))
    public, _ = site.build()
    assert _first() in _shows(ccreel)
    assert "追記した発言" in _page(public, SESSIONS[0])


def test_issue_link_follows_issue_state(site, ccreel):
    _use_sessions(site)
    site.build()
    _shows(ccreel)
    # Issue 01 が消化済みになるとページが消えるので、使い回さずにリンクを外す
    (site.config.parent / "closed").write_text("")
    public, _ = site.build()
    assert _first() in _shows(ccreel)
    page = _page(public, SESSIONS[0])
    assert "issues/me/alpha/01.html" not in page
    assert "<span>#1</span>" in page


def test_expired_sessions_leave_the_cache(site, ccreel):
    _use_sessions(site)
    site.build()
    assert (_cache(site) / f"{_first()}.html").is_file()
    (ccreel / "list.jsonl").write_text(json.dumps(SESSIONS[1]) + "\n")
    public, _ = site.build()
    assert not (_cache(site) / f"{_first()}.html").exists()
    assert not (public / "sessions" / f"{_first()}.html").exists()
    assert _first() not in json.loads((_cache(site) / "index.json").read_text())


def test_session_page_side_has_no_counts(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    side = _page(public, SESSIONS[0]).split('<aside id="side">')[1].split("</aside>")[0]
    assert "All sessions" in side
    assert 'class="m"' not in side


_LINK = re.compile(r"""<[^>]+?\s(?:href|src)="([^"]*)\"""")


def test_links_are_relative_and_resolve(site, ccreel):
    _use_sessions(site)
    public, _ = site.build()
    pages = list((public / "sessions").glob("*.html"))
    assert len(pages) == 3
    # 2回目は使い回したページを書き出す。どちらも同じ条件を満たす
    site.build()
    for page in pages:
        here = posixpath.dirname(page.relative_to(public).as_posix())
        for target in _LINK.findall(page.read_text()):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert not target.startswith("/"), (page.name, target)
            path = target.split("#")[0].split("?")[0]
            resolved = posixpath.normpath(posixpath.join(here, path))
            assert (public / resolved).is_file(), (page.name, target)
