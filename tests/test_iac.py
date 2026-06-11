import pytest
from vaultscan.detectors.iac import scan_dockerfile, scan_github_actions, scan_dotenv
from vaultscan.models import Severity

def test_dockerfile_rules():
    content = """
    FROM ubuntu:latest
    ENV SAFE_VAR
    ENV DB_PASS=supersecret
    ADD http://example.com/file.tar.gz
    RUN curl -s http://example.com | sh
    """
    lines = content.split('\n')
    findings = scan_dockerfile(lines, "Dockerfile", "working_tree")
    
    assert len(findings) == 4
    
    rule_ids = [f["rule_id"] for f in findings]
    assert "docker_from_latest" in rule_ids
    assert "docker_env_value" in rule_ids
    assert "docker_add_http" in rule_ids
    assert "docker_run_curl_sh" in rule_ids
    
    # Check severity
    for f in findings:
        if f["rule_id"] == "docker_run_curl_sh":
            assert f["base_severity"] == Severity.HIGH
        else:
            assert f["base_severity"] == Severity.MEDIUM
            
    # Make sure SAFE_VAR is NOT flagged
    for f in findings:
        assert f["matched_value"] != "ENV SAFE_VAR"

def test_github_actions_rules():
    content = """
    name: Test
    jobs:
      build:
        steps:
          - uses: actions/checkout@v2
          - uses: actions/setup-python@main
          - uses: super/safe-action@a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2
          - run: echo 'hello'
    """
    findings = scan_github_actions(content, ".github/workflows/main.yml", "working_tree")
    
    assert len(findings) == 2
    
    tag_finding = next(f for f in findings if f["rule_id"] == "gha_uses_tag")
    assert tag_finding["matched_value"] == "actions/checkout@v2"
    assert tag_finding["base_severity"] == Severity.MEDIUM
    
    branch_finding = next(f for f in findings if f["rule_id"] == "gha_uses_branch")
    assert branch_finding["matched_value"] == "actions/setup-python@main"
    assert branch_finding["base_severity"] == Severity.CRITICAL

def test_dotenv_tracking():
    # If not tracked, no findings
    f1 = scan_dotenv("SECRET=123", ".env", "working_tree", is_tracked=False)
    assert len(f1) == 0
    
    # If tracked, flag the file
    f2 = scan_dotenv("SECRET=123", ".env", "working_tree", is_tracked=True)
    assert len(f2) == 1
    assert f2[0]["rule_id"] == "tracked_dotenv"
    assert f2[0]["base_severity"] == Severity.CRITICAL
