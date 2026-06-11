import re
from typing import List, Tuple
from ..models import Severity

# Define standard regex patterns
PATTERNS = {
    "aws_access_key": re.compile(r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])"), # Simplified heuristic for AWS AKIA/ASIA
    "aws_specific_key": re.compile(r"(AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    "github_token": re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    "openai_key": re.compile(r"sk-[a-zA-Z0-9]{48}"),
    "stripe_live_key": re.compile(r"sk_live_[0-9a-zA-Z]{24}")
}

def get_base_severity(rule_id: str) -> Severity:
    if rule_id in ("aws_specific_key", "github_token", "openai_key", "stripe_live_key"):
        return Severity.CRITICAL
    return Severity.MEDIUM

def extract_snippet(lines: List[str], line_index: int, context_lines: int = 2) -> str:
    start = max(0, line_index - context_lines)
    end = min(len(lines), line_index + context_lines + 1)
    snippet_lines = lines[start:end]
    return "\n".join(snippet_lines)

def scan_lines(lines: List[str], file_path: str, source: str) -> List[dict]:
    findings_raw = []
    
    for i, line in enumerate(lines):
        line_matches = {}
        for rule_id, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                matched_value = match.group()
                base_sev = get_base_severity(rule_id)
                
                if matched_value not in line_matches:
                    line_matches[matched_value] = {
                        "rule_id": rule_id,
                        "base_severity": base_sev
                    }
                else:
                    if base_sev == Severity.CRITICAL and line_matches[matched_value]["base_severity"] != Severity.CRITICAL:
                        line_matches[matched_value] = {
                            "rule_id": rule_id,
                            "base_severity": base_sev
                        }
                        
        if line_matches:
            snippet = extract_snippet(lines, i)
            for matched_value, info in line_matches.items():
                findings_raw.append({
                    "rule_id": info["rule_id"],
                    "matched_value": matched_value,
                    "file_path": file_path,
                    "line_number": i + 1,
                    "snippet": snippet,
                    "source": source,
                    "base_severity": info["base_severity"]
                })
                
    return findings_raw
