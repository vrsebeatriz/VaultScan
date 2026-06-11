import os
import git
from typing import Dict, List, Optional
from .models import Finding, Occurrence, Severity
from .config import ScanConfig
from .filters import FilterChain
from .detectors.secrets import scan_lines
from .detectors.entropy import calculate_shannon_entropy, get_character_class
from .detectors.iac import scan_dockerfile, scan_github_actions, scan_dotenv
from .severity import compute_severity

class ScanOrchestrator:
    def __init__(self, config: ScanConfig, repo_path: str = None):
        self.config = config
        self.repo_path = repo_path
        self.filter_chain = FilterChain(
            exclude_paths=config.exclude_paths,
            exclude_exts=config.exclude_extensions
        )
        self.findings_map: Dict[str, Finding] = {}
        
        self._repo = None
        if repo_path and os.path.exists(repo_path):
            try:
                self._repo = git.Repo(repo_path)
            except git.exc.InvalidGitRepositoryError:
                pass

    def _is_tracked(self, file_path: str) -> bool:
        if not self._repo or not self.repo_path:
            return False
        try:
            rel_path = os.path.relpath(file_path, self.repo_path).replace('\\', '/')
            for entry in self._repo.index.entries:
                if entry[0] == rel_path:
                    return True
        except ValueError:
            pass
        return False

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
        
        # Only elevate if medium
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
            is_duplicate = any(
                o.file_path == occ.file_path and o.line_number == occ.line_number 
                for o in finding.occurrences
            )
            if not is_duplicate:
                finding.occurrences.append(occ)
            
            if base_severity == Severity.CRITICAL:
                finding.severity = Severity.CRITICAL

    def scan_content(self, text: str, file_path: str, source: str, is_tracked: bool,
                     commit_sha: str = None, commit_date: str = None, commit_message: str = None):
        lines = text.split('\n')
        raw_findings = scan_lines(lines, file_path, source)
        
        filename = os.path.basename(file_path).lower()
        if "dockerfile" in filename:
            raw_findings.extend(scan_dockerfile(lines, file_path, source))
            
        normalized_path = file_path.replace('\\', '/')
        if ".github/workflows/" in normalized_path and (filename.endswith(".yml") or filename.endswith(".yaml")):
            raw_findings.extend(scan_github_actions(text, file_path, source))
            
        if filename == ".env" or filename.endswith(".env"):
            raw_findings.extend(scan_dotenv(text, file_path, source, is_tracked))
            
        for raw in raw_findings:
            if commit_sha:
                raw["commit_sha"] = commit_sha
                raw["commit_date"] = commit_date
                raw["commit_message"] = commit_message
            self.add_raw_finding(raw)

    def scan_file(self, file_path: str):
        if not self.filter_chain.should_scan_file(file_path):
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            return
            
        is_tracked = self._is_tracked(file_path)
        self.scan_content(content, file_path, "working_tree", is_tracked)

    def scan_directory(self, target_dir: str) -> List[Finding]:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                file_path = os.path.join(root, file)
                self.scan_file(file_path)

        final_findings = list(self.findings_map.values())
        for finding in final_findings:
            compute_severity(finding)

        return final_findings
