import uuid
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from typing import Dict, Any

from .config import ScanConfig
from .scanner import ScanOrchestrator
from .git_scanner import GitHistoryScanner

app = FastAPI(title="VaultScan API")

# Global state for a single-user tool
# Keeps track of all scans. However, we only allow 1 scan to run at a time globally.
SCANS: Dict[str, Dict[str, Any]] = {}

class ScanRequest(BaseModel):
    repo_path: str

def run_scan_task(scan_id: str, repo_path: str):
    def progress_callback(pct: int):
        SCANS[scan_id]["progress"] = pct

    try:
        config = ScanConfig()
        
        orchestrator = ScanOrchestrator(config, repo_path=repo_path, progress_callback=progress_callback)
        
        # 1. Working tree scan
        orchestrator.scan_directory(repo_path)
        
        # 2. Git history scan
        git_scanner = GitHistoryScanner(orchestrator, repo_path)
        git_scanner.scan()
        
        findings = list(orchestrator.findings_map.values())
        
        SCANS[scan_id]["status"] = "complete"
        # model_dump is used here so FastAPI serializes it cleanly.
        # model_dump honors the exclude=True on matched_value.
        SCANS[scan_id]["findings"] = [f.model_dump() for f in findings]
        SCANS[scan_id]["progress"] = 100
    except Exception as e:
        SCANS[scan_id]["status"] = "error"
        SCANS[scan_id]["error"] = str(e)

@app.post("/api/scan", status_code=status.HTTP_202_ACCEPTED)
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    for s_id, s_data in SCANS.items():
        if s_data["status"] == "running":
            raise HTTPException(status_code=409, detail="A scan is already in progress.")
            
    if not os.path.exists(req.repo_path):
        raise HTTPException(status_code=400, detail="Invalid repository path.")
        
    scan_id = str(uuid.uuid4())
    SCANS[scan_id] = {
        "status": "running",
        "progress": 0,
        "findings": None,
        "error": None
    }
    
    background_tasks.add_task(run_scan_task, scan_id, req.repo_path)
    return {"scan_id": scan_id}

@app.get("/api/status")
async def get_status(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found.")
    
    scan_data = SCANS[scan_id]
    return {
        "status": scan_data["status"],
        "progress": scan_data["progress"]
    }

@app.get("/api/report")
async def get_report(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found.")
        
    scan_data = SCANS[scan_id]
    if scan_data["status"] == "error":
        raise HTTPException(status_code=500, detail=scan_data.get("error", "Unknown error during scan."))
    elif scan_data["status"] != "complete":
        raise HTTPException(status_code=400, detail="Scan is not complete yet.")
        
    return {"findings": scan_data["findings"]}
