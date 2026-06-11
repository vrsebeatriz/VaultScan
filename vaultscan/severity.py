from .models import Severity, Finding, Occurrence

def compute_occurrence_severity(occurrence: Occurrence, base_severity: Severity) -> Severity:
    path = occurrence.file_path.replace('\\', '/').lower()
    
    demote_keywords = ["test", "docs", ".spec.", "fixture", "mock", "readme"]
    
    is_demoted = False
    for kw in demote_keywords:
        if kw in path:
            is_demoted = True
            break
            
    current_sev = base_severity
    if occurrence.source == "git_history":
        if current_sev == Severity.CRITICAL:
            current_sev = Severity.HIGH
        elif current_sev == Severity.HIGH:
            current_sev = Severity.MEDIUM
        elif current_sev == Severity.MEDIUM:
            current_sev = Severity.LOW
            
    if is_demoted:
        current_sev = Severity.LOW
        
    return current_sev

def compute_severity(finding: Finding) -> Severity:
    """
    Computes severity for all occurrences and sets the finding's max severity.
    """
    if not finding.occurrences:
        return finding.severity
        
    max_sev = Severity.LOW
    severity_order = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}
    
    for occ in finding.occurrences:
        occ_sev = compute_occurrence_severity(occ, finding.severity)
        if severity_order[occ_sev] > severity_order[max_sev]:
            max_sev = occ_sev
            
    finding.severity = max_sev
    return finding.severity
