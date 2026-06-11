import uuid
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any

from .config import ScanConfig
from .scanner import ScanOrchestrator
from .git_scanner import GitHistoryScanner

app = FastAPI(title="VaultScan API")

# Ensure static directory exists relative to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

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
        
        findings = orchestrator.finalize()
        
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

@app.get("/api/export")
async def export_report(scan_id: str, format: str = "json"):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found.")
        
    scan_data = SCANS[scan_id]
    if scan_data["status"] != "complete":
        raise HTTPException(status_code=400, detail="Scan is not complete yet.")
        
    findings = scan_data["findings"]
    
    if format == "json":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={"findings": findings},
            headers={"Content-Disposition": "attachment; filename=vaultscan_report.json"}
        )
    elif format == "html":
        from fastapi.responses import HTMLResponse
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>VaultScan Report</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; }}
        .warning {{ background-color: #ffebee; color: #c62828; padding: 15px; border-left: 5px solid #c62828; font-weight: bold; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="warning">WARNING: DO NOT COMMIT THIS FILE. IT MAY CONTAIN SENSITIVE (THOUGH PARTIALLY MASKED) INFORMATION.</div>
    <h1>VaultScan Report</h1>
    <p>Total Findings: {len(findings)}</p>
    <table>
        <tr>
            <th>Rule ID</th>
            <th>Severity</th>
            <th>Masked Value</th>
            <th>Occurrences</th>
        </tr>
"""
        for f in findings:
            occurrences_text = "<br>".join([f"{o['file_path']}:{o['line_number']} ({o['source']})" for o in f["occurrences"]])
            html_content += f"""
        <tr>
            <td>{f['rule_id']}</td>
            <td>{f['severity']}</td>
            <td><code>{f['masked_value']}</code></td>
            <td>{occurrences_text}</td>
        </tr>
"""
        html_content += """
    </table>
</body>
</html>
"""
        return HTMLResponse(
            content=html_content,
            headers={"Content-Disposition": "attachment; filename=vaultscan_report.html"}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'json' or 'html'.")
