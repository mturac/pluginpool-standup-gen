"""Tests for standup.py — hermetic temp git repos, no network."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "standup.py"


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test User"
    env["GIT_AUTHOR_EMAIL"] = "test@pluginpool.local"
    env["GIT_COMMITTER_NAME"] = "Test User"
    env["GIT_COMMITTER_EMAIL"] = "test@pluginpool.local"
    res = subprocess.run(
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    )
    return res.stdout


def _seed(repo: Path, n_commits: int = 2) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@pluginpool.local")
    _git(repo, "config", "user.name", "Test User")
    for i in range(n_commits):
        f = repo / f"f{i}.txt"
        f.write_text(f"v{i}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", f"feat: change {i}")


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_works():
    r = _run("--help")
    assert r.returncode == 0
    assert "standup" in r.stdout.lower()


def test_collects_commits_from_seeded_repo(tmp_path):
    repo = tmp_path / "repo"
    _seed(repo, 3)
    r = _run("--repos", str(repo), "--since", "2000-01-01", "--until", "none", "--author", "all", cwd=repo)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert len(data["repos"]) == 1
    assert len(data["repos"][0]["commits"]) == 3
    assert all("hash" in c and "subject" in c for c in data["repos"][0]["commits"])


def test_markdown_has_yesterday_today_blockers(tmp_path):
    repo = tmp_path / "repo"
    _seed(repo, 1)
    r = _run("--repos", str(repo), "--since", "2000-01-01", "--until", "none", "--author", "all", "--format", "md", cwd=repo)
    assert r.returncode == 0, r.stderr
    md = r.stdout
    assert "## Yesterday" in md
    assert "## Today (planned)" in md
    assert "## Blockers" in md


def test_since_yesterday_resolves_to_business_day(tmp_path):
    from scripts.standup import _parse_since, _last_business_day
    monday = dt.date(2026, 5, 18)
    assert _last_business_day(monday) == dt.date(2026, 5, 15)
    midweek = dt.date(2026, 5, 20)
    assert _last_business_day(midweek) == dt.date(2026, 5, 19)
    sunday = dt.date(2026, 5, 17)
    assert _last_business_day(sunday) == dt.date(2026, 5, 15)
    assert _parse_since("yesterday", today=monday) == "2026-05-15"
    assert _parse_since("2026-04-01", today=monday) == "2026-04-01"


def test_multi_repo(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    _seed(a, 1)
    _seed(b, 2)
    r = _run("--repos", f"{a},{b}", "--since", "2000-01-01", "--until", "none", "--author", "all", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    paths = {os.path.basename(rep["path"]) for rep in data["repos"]}
    assert paths == {"a", "b"}
    counts = sorted(len(rep["commits"]) for rep in data["repos"])
    assert counts == [1, 2]


def test_author_filter(tmp_path):
    repo = tmp_path / "repo"
    _seed(repo, 1)
    # Add a commit by a different author
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Other",
        "GIT_AUTHOR_EMAIL": "other@example.com",
        "GIT_COMMITTER_NAME": "Other",
        "GIT_COMMITTER_EMAIL": "other@example.com",
    })
    (repo / "z.txt").write_text("z\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feat: other"], cwd=repo, env=env, check=True)

    r = _run("--repos", str(repo), "--since", "2000-01-01", "--until", "none", "--author", "test@pluginpool.local", cwd=repo)
    data = json.loads(r.stdout)
    subjects = [c["subject"] for c in data["repos"][0]["commits"]]
    assert "feat: other" not in subjects

    r2 = _run("--repos", str(repo), "--since", "2000-01-01", "--until", "none", "--author", "all", cwd=repo)
    data2 = json.loads(r2.stdout)
    subjects2 = [c["subject"] for c in data2["repos"][0]["commits"]]
    assert "feat: other" in subjects2


def test_empty_repo_is_graceful(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    r = _run("--repos", str(repo), "--since", "2000-01-01", "--until", "none", "--author", "all", cwd=repo)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["repos"][0]["commits"] == []


def test_default_until_excludes_today(tmp_path):
    """Default --until is today 00:00, so commits made today should NOT appear."""
    repo = tmp_path / "repo"
    _seed(repo, 1)
    r = _run("--repos", str(repo), "--since", "2000-01-01", "--author", "all", cwd=repo)
    data = json.loads(r.stdout)
    today = dt.date.today().isoformat()
    dates = [c["date"] for c in data["repos"][0]["commits"]]
    assert today not in dates, f"today's commits should be excluded by default --until, got {dates}"
