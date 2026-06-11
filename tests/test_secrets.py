import pytest
from vaultscan.detectors.entropy import calculate_shannon_entropy, get_character_class
from vaultscan.detectors.secrets import scan_lines
from vaultscan.scanner import ScanOrchestrator
from vaultscan.config import ScanConfig

def test_entropy_calculator():
    # Low entropy
    e1 = calculate_shannon_entropy("aaaaaaaa")
    assert e1 == 0.0
    
    # High entropy hex
    e2 = calculate_shannon_entropy("a1b2c3d4e5f6")
    assert e2 > 2.0
    assert get_character_class("a1b2c3d4e5f6") == "hex"

def test_scan_lines_regex():
    lines = [
        "def test():",
        "    aws_key = 'AKIAIOSFODNN7EXAMPLX'", # Slightly changed so it's not fake value in filter check (scanner does fake check)
        "    pass"
    ]
    raw = scan_lines(lines, "main.py", "working_tree")
    assert len(raw) == 1
    assert raw[0]["rule_id"] == "aws_specific_key"
    assert raw[0]["matched_value"] == "AKIAIOSFODNN7EXAMPLX"
    assert raw[0]["line_number"] == 2
    assert "def test():" in raw[0]["snippet"]

def test_scanner_deduplication(tmp_path):
    # Create two files with the same secret
    file1 = tmp_path / "file1.py"
    file1.write_text("aws_key = 'AKIA1234567890123456'")
    
    file2 = tmp_path / "file2.py"
    file2.write_text("another_aws_key = 'AKIA1234567890123456'")
    
    orchestrator = ScanOrchestrator(ScanConfig())
    orchestrator.scan_file(str(file1))
    orchestrator.scan_file(str(file2))
    
    findings = list(orchestrator.findings_map.values())
    assert len(findings) == 1 # Deduplicated
    assert len(findings[0].occurrences) == 2
    
def test_fake_value_denylist(tmp_path):
    file = tmp_path / "fake.py"
    file.write_text("aws_key = 'AKIAIOSFODNN7EXAMPLE'")
    
    orchestrator = ScanOrchestrator(ScanConfig())
    orchestrator.scan_file(str(file))
    
    findings = list(orchestrator.findings_map.values())
    assert len(findings) == 0 # Filtered out
