from vaultscan.models import Finding, Severity, Occurrence
from vaultscan.severity import compute_severity

def test_compute_severity_demotion_git_history():
    f = Finding(
        rule_id="test",
        matched_value="secret",
        severity=Severity.CRITICAL,
        occurrences=[
            Occurrence(file_path="src/main.py", line_number=1, source="git_history")
        ]
    )
    new_sev = compute_severity(f)
    assert new_sev == Severity.HIGH
    assert f.severity == Severity.HIGH

def test_compute_severity_demotion_test_path():
    f = Finding(
        rule_id="test",
        matched_value="secret",
        severity=Severity.CRITICAL,
        occurrences=[
            Occurrence(file_path="test/integration.py", line_number=1, source="working_tree")
        ]
    )
    new_sev = compute_severity(f)
    assert new_sev == Severity.LOW
    assert f.severity == Severity.LOW

def test_compute_severity_combined_demotion():
    f = Finding(
        rule_id="test",
        matched_value="secret",
        severity=Severity.MEDIUM,
        occurrences=[
            Occurrence(file_path="docs/setup.md", line_number=1, source="git_history")
        ]
    )
    new_sev = compute_severity(f)
    # Both git_history and docs/ apply, test paths always force LOW
    assert new_sev == Severity.LOW
    assert f.severity == Severity.LOW

def test_compute_severity_max_over_occurrences():
    f = Finding(
        rule_id="test",
        matched_value="secret",
        severity=Severity.CRITICAL,
        occurrences=[
            Occurrence(file_path="test/integration.py", line_number=1, source="working_tree"), # LOW
            Occurrence(file_path="src/main.py", line_number=1, source="git_history") # HIGH
        ]
    )
    new_sev = compute_severity(f)
    assert new_sev == Severity.HIGH
    assert f.severity == Severity.HIGH
