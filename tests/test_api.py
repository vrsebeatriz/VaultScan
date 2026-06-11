import pytest
from fastapi.testclient import TestClient
import git
import os
from vaultscan.api import app, SCANS

@pytest.fixture
def client():
    # Clear global state before each test
    SCANS.clear()
    return TestClient(app)

@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    repo = git.Repo.init(str(repo_dir))
    file1 = repo_dir / "main.py"
    file1.write_text("aws_key = 'AKIAIOSFODNN7EXAMPLX'")
    repo.index.add([str(file1)])
    repo.index.commit("Initial commit with secret")
    return str(repo_dir)

def test_scan_flow(client, temp_repo):
    # 1. Start scan
    response = client.post("/api/scan", json={"repo_path": temp_repo})
    assert response.status_code == 202
    data = response.json()
    assert "scan_id" in data
    scan_id = data["scan_id"]
    
    # 2. Check status 
    # BackgroundTasks in TestClient run synchronously right after the response is sent.
    # Therefore, by the time we call GET /api/status, the task is already finished.
    status_resp = client.get(f"/api/status?scan_id={scan_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "complete"
    assert status_resp.json()["progress"] == 100
    
    # 3. Check report
    report_resp = client.get(f"/api/report?scan_id={scan_id}")
    assert report_resp.status_code == 200
    findings = report_resp.json()["findings"]
    assert len(findings) == 1
    
    finding = findings[0]
    # Verify masked value is present but not matched_value
    assert "matched_value" not in finding
    assert finding["masked_value"] == "AKIA****MPLX"

    # 4. Check export JSON
    json_export = client.get(f"/api/export?scan_id={scan_id}&format=json")
    assert json_export.status_code == 200
    assert json_export.headers["Content-Disposition"].startswith("attachment; filename=vaultscan_report.json")
    assert "AKIA****MPLX" in json_export.text
    
    # 5. Check export HTML
    html_export = client.get(f"/api/export?scan_id={scan_id}&format=html")
    assert html_export.status_code == 200
    assert html_export.headers["Content-Disposition"].startswith("attachment; filename=vaultscan_report.html")
    assert "WARNING: DO NOT COMMIT THIS FILE" in html_export.text
    assert "AKIA****MPLX" in html_export.text

def test_scan_conflict(client, temp_repo):
    # Manually inject a running scan
    SCANS["fake_id"] = {"status": "running"}
    
    response = client.post("/api/scan", json={"repo_path": temp_repo})
    assert response.status_code == 409
    
def test_invalid_path(client):
    response = client.post("/api/scan", json={"repo_path": "/invalid/path/that/does/not/exist"})
    assert response.status_code == 400
