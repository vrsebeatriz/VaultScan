import pytest
import git
import os
from vaultscan.config import ScanConfig
from vaultscan.scanner import ScanOrchestrator
from vaultscan.git_scanner import GitHistoryScanner

@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    repo = git.Repo.init(str(repo_dir))
    
    # Commit 1
    file1 = repo_dir / "main.py"
    file1.write_text("aws_key = 'AKIAIOSFODNN7EXAMPLX'")
    repo.index.add([str(file1)])
    commit1 = repo.index.commit("Initial commit with secret")
    
    # Commit 2
    file2 = repo_dir / "utils.py"
    file2.write_text("print('hello')")
    repo.index.add([str(file2)])
    commit2 = repo.index.commit("Add utils")
    
    return str(repo_dir), repo, [commit1, commit2]

def test_git_history_scanner(temp_repo):
    repo_path, repo, commits = temp_repo
    
    orchestrator = ScanOrchestrator(ScanConfig())
    git_scanner = GitHistoryScanner(orchestrator, repo_path)
    
    git_scanner.scan()
    
    findings = list(orchestrator.findings_map.values())
    assert len(findings) == 1
    finding = findings[0]
    
    assert finding.matched_value == "AKIAIOSFODNN7EXAMPLX"
    assert len(finding.occurrences) == 1
    occ = finding.occurrences[0]
    assert occ.source == "git_history"
    assert occ.commit_sha == commits[0].hexsha
    assert occ.commit_message == "Initial commit with secret"
    # paths in git are normalized
    assert occ.file_path == "main.py"

def test_git_history_deduplication(temp_repo):
    repo_path, repo, commits = temp_repo
    
    # Commit 3 changes main.py but keeps the secret on the same line
    file1 = os.path.join(repo_path, "main.py")
    with open(file1, "a") as f:
        f.write("\nprint('test')")
    
    repo.index.add([file1])
    commit3 = repo.index.commit("Modify main.py")
    
    orchestrator = ScanOrchestrator(ScanConfig())
    git_scanner = GitHistoryScanner(orchestrator, repo_path)
    
    git_scanner.scan()
    
    findings = list(orchestrator.findings_map.values())
    assert len(findings) == 1
    finding = findings[0]
    
    # Should only have 1 occurrence because we deduplicate by line_number and file_path!
    assert len(finding.occurrences) == 1
    # The first time we scan it forwards is in commit 1, so the metadata should be commit1's!
    occ = finding.occurrences[0]
    assert occ.commit_sha == commits[0].hexsha
    
def test_git_history_max_commits(temp_repo, caplog):
    repo_path, repo, commits = temp_repo
    
    config = ScanConfig(max_commits=1)
    orchestrator = ScanOrchestrator(config)
    git_scanner = GitHistoryScanner(orchestrator, repo_path)
    
    git_scanner.scan()
    
    # The warning should be generated
    assert "Git history exceeds cap" in caplog.text
