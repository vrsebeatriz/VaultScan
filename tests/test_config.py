import pytest
import os
from vaultscan.config import ScanConfig, load_config
import logging

def test_default_config():
    config = ScanConfig()
    assert config.max_commits == 500
    assert config.entropy_threshold.hex == 3.0

def test_env_override(monkeypatch):
    monkeypatch.setenv("VAULTSCAN_MAX_COMMITS", "100")
    config = ScanConfig()
    assert config.max_commits == 100

def test_unknown_keys_warning(caplog):
    # Setting an unknown env var won't trigger validation warnings 
    # unless we pass it to the constructor.
    # Pydantic v2 SettingsConfigDict with extra='allow' will keep extra fields.
    with caplog.at_level(logging.WARNING):
        config = ScanConfig(unknown_key="value", max_commits=200)
    
    assert "Unknown configuration key ignored: unknown_key" in caplog.text
    assert config.max_commits == 200

def test_load_config_yaml(tmp_path):
    import yaml
    p = tmp_path / "vaultscan.yml"
    p.write_text("max_commits: 150\nexclude_paths:\n  - custom_dir\n")
    
    config = load_config(str(p))
    assert config.max_commits == 150
    assert "custom_dir" in config.exclude_paths
