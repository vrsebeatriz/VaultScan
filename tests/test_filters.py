from vaultscan.filters import FilterChain

def test_mandatory_excludes():
    fc = FilterChain()
    
    # Path excludes
    assert not fc.should_scan_file("node_modules/package/index.js")
    assert not fc.should_scan_file("src/.git/config")
    assert not fc.should_scan_file("build/output.txt")
    
    # Extension excludes
    assert not fc.should_scan_file("yarn.lock")
    assert not fc.should_scan_file("Cargo.lock")
    assert not fc.should_scan_file("app.min.js")
    
    # Should scan
    assert fc.should_scan_file("src/main.py")
    assert fc.should_scan_file("README.md")

def test_custom_excludes():
    fc = FilterChain(exclude_paths=["custom_ignore"], exclude_exts=[".xyz"])
    
    assert not fc.should_scan_file("custom_ignore/file.txt")
    assert not fc.should_scan_file("file.xyz")
    # Mandatory should still work
    assert not fc.should_scan_file(".git/HEAD")

def test_fake_values():
    fc = FilterChain()
    assert fc.is_fake_value("AKIAIOSFODNN7EXAMPLE")
    assert not fc.is_fake_value("AKIAREALKEYTHATSVALD")
