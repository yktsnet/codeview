"""設定の隣に置いた拡張と、アカウントの数・取り込み元の設定を確かめる。"""

from __future__ import annotations

import textwrap

# 本体の外に置く Issue の取り込み元。リポごとに1本返し、2本目は1本目を待つ
SOURCE = '''
from codeview.issues import Issue, Wait


def issues(ctx, account, repos):
    found = []
    for repo in repos:
        first = Issue(
            account=account.name, repo=repo.path.name, slug=repo.slug, ref="1",
            title="ext first " + ctx.options["label"], kind="", state="Open", updated=2,
            body="<b>raw</b>", targets=["main.py"],
        )
        second = Issue(
            account=account.name, repo=repo.path.name, slug=repo.slug, ref="2",
            title="ext second", kind="", state="Draft", updated=1,
            waits=[Wait(repo.path.name, "1"), Wait(repo.path.name, "99")],
        )
        found += [first, second]
    return found
'''


def _use_source(site, module: str) -> None:
    text = site.config.read_text().replace(
        'groups = ["own"]\n', f'groups = ["own"]\nissues = "{module}"\n'
    )
    site.write_config(text + f'\n[plugins]\nmodules = ["{module}"]\n\n[plugins.{module}]\nlabel = "ok"\n')


def test_issue_source_next_to_config(site):
    (site.config.parent / "extsrc.py").write_text(SOURCE)
    _use_source(site, "extsrc")
    public, _ = site.build()
    listing = (public / "issues" / "me" / "index.html").read_text()
    assert "ext first ok" in listing and "ext second" in listing
    second = (public / "issues" / "me" / "alpha" / "2.html").read_text()
    assert "waits on alpha #1" in second
    # 一覧に無い先への依存は落とす
    assert "#99" not in second
    # 取り込み元が trusted を立てなければ、本文の HTML はエスケープされる
    first = (public / "issues" / "me" / "alpha" / "1.html").read_text()
    assert "<b>raw</b>" not in first
    assert "/issues/me/alpha/1.html" in (public / "alpha" / "main.py.html").read_text()


def test_issue_source_must_be_listed_plugin(site):
    site.write_config(
        site.config.read_text().replace('groups = ["own"]\n', 'groups = ["own"]\nissues = "extsrc"\n')
    )
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr and "issues" in proc.stderr
    assert not public.exists()


def test_issue_source_needs_issues_function(site):
    (site.config.parent / "noissues.py").write_text("def css(ctx):\n    return ''\n")
    _use_source(site, "noissues")
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "no issues()" in proc.stderr
    assert not public.exists()


def test_at_most_two_accounts(site):
    site.write_config(
        site.config.read_text()
        + textwrap.dedent(
            """
            [[accounts]]
            name = "third"
            hosts = ["example.invalid"]
            """
        )
    )
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "1 to 2" in proc.stderr
    assert not public.exists()


def test_gh_config_dir_only_for_github(site):
    site.write_config(
        site.config.read_text().replace(
            'groups = ["own"]\n', 'groups = ["own"]\nissues = "extsrc"\ngh_config_dir = "/tmp/x"\n'
        )
        + '\n[plugins]\nmodules = ["extsrc"]\n'
    )
    (site.config.parent / "extsrc.py").write_text(SOURCE)
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "gh_config_dir" in proc.stderr
