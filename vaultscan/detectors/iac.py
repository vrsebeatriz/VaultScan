import re
import yaml
from typing import List
from ..models import Severity

# Dockerfile rules
DOCKER_ENV_REGEX = re.compile(r"^\s*ENV\s+[A-Za-z0-9_]+\s*=\s*(.+)$")
DOCKER_FROM_LATEST_REGEX = re.compile(r"^\s*FROM\s+[^:]+:latest\s*$", re.IGNORECASE)
DOCKER_ADD_HTTP_REGEX = re.compile(r"^\s*ADD\s+https?://\S+", re.IGNORECASE)
DOCKER_RUN_CURL_SH_REGEX = re.compile(r"^\s*RUN\s+.*curl.*\|.*sh", re.IGNORECASE)

def _create_finding(rule_id: str, matched_value: str, file_path: str, line_index: int, lines: List[str], source: str, severity: Severity) -> dict:
    start = max(0, line_index - 2)
    end = min(len(lines), line_index + 3)
    snippet = "\n".join(lines[start:end])
    return {
        "rule_id": rule_id,
        "matched_value": matched_value.strip(),
        "file_path": file_path,
        "line_number": line_index + 1,
        "snippet": snippet,
        "source": source,
        "base_severity": severity
    }

def scan_dockerfile(lines: List[str], file_path: str, source: str) -> List[dict]:
    findings = []
    for i, line in enumerate(lines):
        if DOCKER_ENV_REGEX.match(line):
            findings.append(_create_finding("docker_env_value", line, file_path, i, lines, source, Severity.MEDIUM))
        if DOCKER_FROM_LATEST_REGEX.match(line):
            findings.append(_create_finding("docker_from_latest", line, file_path, i, lines, source, Severity.MEDIUM))
        if DOCKER_ADD_HTTP_REGEX.match(line):
            findings.append(_create_finding("docker_add_http", line, file_path, i, lines, source, Severity.MEDIUM))
        if DOCKER_RUN_CURL_SH_REGEX.match(line):
            findings.append(_create_finding("docker_run_curl_sh", line, file_path, i, lines, source, Severity.HIGH))
    return findings

def _find_line_index(lines: List[str], text: str) -> int:
    for i, line in enumerate(lines):
        if text in line:
            return i
    return 0

def scan_github_actions(yaml_content: str, file_path: str, source: str) -> List[dict]:
    findings = []
    lines = yaml_content.split('\n')
    try:
        data = yaml.safe_load(yaml_content)
    except Exception:
        return findings

    if not isinstance(data, dict):
        return findings

    def find_uses(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "uses" and isinstance(v, str) and "@" in v:
                    action, ref = v.split("@", 1)
                    if re.match(r"^[0-9a-f]{40}$", ref):
                        pass # SAFE
                    elif re.match(r"^v\d+(\.\d+)*$", ref):
                        line_index = _find_line_index(lines, v)
                        findings.append(_create_finding("gha_uses_tag", v, file_path, line_index, lines, source, Severity.MEDIUM))
                    else:
                        line_index = _find_line_index(lines, v)
                        findings.append(_create_finding("gha_uses_branch", v, file_path, line_index, lines, source, Severity.CRITICAL))
                else:
                    find_uses(v)
        elif isinstance(node, list):
            for item in node:
                find_uses(item)

    find_uses(data)
    return findings

def scan_dotenv(content: str, file_path: str, source: str, is_tracked: bool) -> List[dict]:
    findings = []
    if is_tracked:
        lines = content.split('\n')
        findings.append(_create_finding("tracked_dotenv", "Tracked .env file", file_path, 0, lines, source, Severity.CRITICAL))
    return findings
