from vaultscan.models import Finding, Severity, Occurrence

def test_finding_masking():
    # Long secret
    f1 = Finding(
        rule_id="test",
        matched_value="AKIAIOSFODNN7EXAMPLE",
    )
    assert f1.masked_value == "AKIA****MPLE"
    
    # Short secret
    f2 = Finding(
        rule_id="test",
        matched_value="secret",
    )
    assert f2.masked_value == "******"

def test_matched_value_excluded_from_dump():
    f = Finding(
        rule_id="test",
        matched_value="super_secret_value",
        occurrences=[Occurrence(file_path="foo.txt", line_number=1)]
    )
    dump = f.model_dump()
    assert "matched_value" not in dump
    assert dump["masked_value"] == "supe****alue"
    
    json_dump = f.model_dump_json()
    assert "super_secret_value" not in json_dump
    assert "supe****alue" in json_dump
