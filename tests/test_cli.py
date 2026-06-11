import pytest
import os
import git
from vaultscan.cli import run_headless_scan

@pytest.fixture
def clean_repo(tmp_path):
    repo_dir = tmp_path / "repo_clean"
    repo_dir.mkdir()
    repo = git.Repo.init(str(repo_dir))
    file1 = repo_dir / "main.py"
    file1.write_text("print('hello world')")
    repo.index.add([str(file1)])
    repo.index.commit("Initial commit")
    return str(repo_dir)

@pytest.fixture
def dirty_repo(tmp_path):
    repo_dir = tmp_path / "repo_dirty"
    repo_dir.mkdir()
    repo = git.Repo.init(str(repo_dir))
    file1 = repo_dir / "main.py"
    file1.write_text("aws_key = 'AKIAIOSFODNN7EXAMPLX'")
    repo.index.add([str(file1)])
    repo.index.commit("Initial commit with secret")
    return str(repo_dir)

def test_headless_clean(clean_repo):
    exit_code = run_headless_scan(clean_repo)
    assert exit_code == 0

def test_headless_dirty(dirty_repo):
    exit_code = run_headless_scan(dirty_repo)
    assert exit_code == 1

def test_headless_invalid_path():
    exit_code = run_headless_scan("/invalid/path/123")
    assert exit_code == 1
