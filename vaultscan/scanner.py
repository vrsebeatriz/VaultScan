import os
from typing import Dict, List
from .models import Finding, Occurrence, Severity
from .config import ScanConfig
from .filters import FilterChain
from .detectors.secrets import scan_lines
from .detectors.entropy import calculate_shannon_entropy, get_character_class
from .severity import compute_severity

class ScanOrchestrator:
    def __init__(self, config: ScanConfig):
        self.config = config
        self.filter_chain = FilterChain(
            exclude_paths=config.exclude_paths,
            exclude_exts=config.exclude_extensions
        )
        self.findings_map: Dict[str, Finding] = {}

    def add_raw_finding(self, raw: dict):
        matched_value = raw["matched_value"]
        
        # Check fake values denylist
        if self.filter_chain.is_fake_value(matched_value):
            return

        # Entropy elevation
        base_severity = raw["base_severity"]
        entropy = calculate_shannon_entropy(matched_value)
        char_class = get_character_class(matched_value)
        
        threshold = self.config.entropy_threshold.hex if char_class == "hex" else self.config.entropy_threshold.base64
        
        # Only elevate regex matches if entropy is very high
        if entropy > threshold and base_severity == Severity.MEDIUM:
            base_severity = Severity.HIGH

        occ = Occurrence(
            file_path=raw["file_path"],
            line_number=raw["line_number"],
            snippet=raw["snippet"],
            source=raw["source"],
            commit_sha=raw.get("commit_sha"),
            commit_date=raw.get("commit_date"),
            commit_message=raw.get("commit_message")
        )

        if matched_value not in self.findings_map:
            self.findings_map[matched_value] = Finding(
                rule_id=raw["rule_id"],
                matched_value=matched_value,
                severity=base_severity,
                occurrences=[occ]
            )
        else:
            finding = self.findings_map[matched_value]
            # Deduplicate occurrence
            is_duplicate = any(
                o.file_path == occ.file_path and o.line_number == occ.line_number 
                for o in finding.occurrences
            )
            if not is_duplicate:
                finding.occurrences.append(occ)
            
            # Potentially update base severity if a stronger rule matched
            if base_severity == Severity.CRITICAL:
                finding.severity = Severity.CRITICAL

    def scan_file(self, file_path: str):
        if not self.filter_chain.should_scan_file(file_path):
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Skip binary or non-utf8 files
            return
            
        lines = content.split('\n')
        raw_findings = scan_lines(lines, file_path, "working_tree")
        for raw in raw_findings:
            self.add_raw_finding(raw)

    def scan_directory(self, target_dir: str) -> List[Finding]:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Ensure we use relative-like paths for filter checks if we want
                self.scan_file(file_path)

        # Compute final severities
        final_findings = list(self.findings_map.values())
        for finding in final_findings:
            compute_severity(finding)

        return final_findings
