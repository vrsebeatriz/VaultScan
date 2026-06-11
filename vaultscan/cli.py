import argparse
import sys
import threading
import time
import webbrowser
import os
import uvicorn
import urllib.request
import json

from vaultscan.config import ScanConfig
from vaultscan.scanner import ScanOrchestrator
from vaultscan.git_scanner import GitHistoryScanner

def run_headless_scan(repo_path: str) -> int:
    """Run scan synchronously without API, print results to console, and return exit code."""
    print(f"Starting VaultScan headless mode on: {repo_path}")
    if not os.path.exists(repo_path):
        print("Error: Invalid repository path.")
        return 1
        
    config = ScanConfig()
    orchestrator = ScanOrchestrator(config, repo_path=repo_path)
    
    print("Scanning working tree...")
    orchestrator.scan_directory(repo_path)
    
    print("Scanning git history...")
    git_scanner = GitHistoryScanner(orchestrator, repo_path)
    git_scanner.scan()
    
    findings = list(orchestrator.findings_map.values())
    
    print(f"\nScan complete. Found {len(findings)} unique secret/IaC issues.")
    for f in findings:
        print(f"[{f.severity.value}] {f.rule_id} -> {f.masked_value} ({len(f.occurrences)} occurrences)")
        
    if len(findings) > 0:
        return 1
    return 0

def run_server():
    from vaultscan.api import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def main():
    parser = argparse.ArgumentParser(description="VaultScan - Local secrets and IaC scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    scan_parser = subparsers.add_parser("scan", help="Scan a local Git repository")
    scan_parser.add_argument("repo_path", help="Absolute path to the repository")
    scan_parser.add_argument("--headless", action="store_true", help="Run without starting the Web Dashboard. Returns exit code 1 if findings exist.")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        repo_path = os.path.abspath(args.repo_path)
        
        if args.headless:
            exit_code = run_headless_scan(repo_path)
            sys.exit(exit_code)
        else:
            print(f"Starting VaultScan Server for: {repo_path}")
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            # Wait for server to start
            time.sleep(2)
            
            # Automatically start the scan via API
            scan_id = None
            try:
                data = json.dumps({"repo_path": repo_path}).encode("utf-8")
                req = urllib.request.Request("http://127.0.0.1:8000/api/scan", data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as res:
                    if res.status == 202:
                        res_body = json.loads(res.read().decode('utf-8'))
                        scan_id = res_body.get("scan_id")
                        print("Scan triggered successfully.")
            except Exception as e:
                print(f"Error communicating with local API: {e}")
            
            print("Opening Web Dashboard... Press Ctrl+C to stop the server.")
            webbrowser.open("http://127.0.0.1:8000")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down VaultScan server.")
                
                # Fetch report to determine exit code before shutting down
                exit_code = 0
                try:
                    if scan_id:
                        req_status = urllib.request.Request(f"http://127.0.0.1:8000/api/status?scan_id={scan_id}")
                        with urllib.request.urlopen(req_status) as res:
                            status_data = json.loads(res.read().decode('utf-8'))
                            if status_data.get("status") == "complete":
                                req_report = urllib.request.Request(f"http://127.0.0.1:8000/api/report?scan_id={scan_id}")
                                with urllib.request.urlopen(req_report) as rep:
                                    report_data = json.loads(rep.read().decode('utf-8'))
                                    findings = report_data.get("findings", [])
                                    if len(findings) > 0:
                                        exit_code = 1
                except Exception:
                    pass
                sys.exit(exit_code)

if __name__ == "__main__":
    main()
