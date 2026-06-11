import git
import logging
from typing import Optional
from .scanner import ScanOrchestrator
from .detectors.secrets import scan_lines

logger = logging.getLogger(__name__)

class GitHistoryScanner:
    def __init__(self, orchestrator: ScanOrchestrator, repo_path: str):
        self.orchestrator = orchestrator
        self.repo_path = repo_path
        
    def scan(self):
        try:
            repo = git.Repo(self.repo_path)
        except git.exc.InvalidGitRepositoryError:
            logger.warning(f"Path '{self.repo_path}' is not a valid git repository. Skipping git history scan.")
            if self.orchestrator.progress_callback:
                self.orchestrator.progress_callback(100)
            return

        try:
            # We reverse the commits to scan from oldest to newest (forwards).
            # This ensures the recorded commit metadata in Occurrence represents the *introduction* of the secret.
            commits = list(repo.iter_commits('HEAD'))
            commits_to_scan = list(reversed(commits))
            
            if len(commits_to_scan) > self.orchestrator.config.max_commits:
                logger.warning(f"Git history exceeds cap ({len(commits_to_scan)} > {self.orchestrator.config.max_commits}). Truncating scan to first {self.orchestrator.config.max_commits} commits.")
                # If we want the oldest N commits, we slice after reverse:
                commits_to_scan = commits_to_scan[:self.orchestrator.config.max_commits]
        except git.exc.GitCommandError as e:
            logger.error(f"Error fetching git history: {e}")
            if self.orchestrator.progress_callback:
                self.orchestrator.progress_callback(100)
            return
            
        total = len(commits_to_scan)
        for i, commit in enumerate(commits_to_scan):
            self._scan_commit(repo, commit)
            if self.orchestrator.progress_callback and total > 0:
                self.orchestrator.progress_callback(50 + int((i + 1) / total * 50))
            
    def _scan_commit(self, repo: git.Repo, commit: git.Commit):
        commit_date = commit.committed_datetime.isoformat()
        commit_msg = commit.message.strip().split('\n')[0] # First line
        commit_sha = commit.hexsha
        
        if not commit.parents:
            # Initial commit, scan the entire tree
            for item in commit.tree.traverse():
                if item.type == 'blob':
                    file_path = item.path
                    if not self.orchestrator.filter_chain.should_scan_file(file_path):
                        continue
                    try:
                        blob_data = item.data_stream.read()
                        text = blob_data.decode('utf-8')
                        self._process_blob_text(text, file_path, commit_sha, commit_date, commit_msg)
                    except Exception as e:
                        logger.debug(f"Error reading blob for {file_path} in {commit_sha}: {e}")
        else:
            diffs = commit.parents[0].diff(commit, create_patch=False)
            for diff in diffs:
                if diff.change_type in ['D']:
                    continue
                    
                file_path = diff.b_path
                if not self.orchestrator.filter_chain.should_scan_file(file_path):
                    continue
                    
                try:
                    blob = diff.b_blob
                    if blob is None:
                        continue
                    blob_data = blob.data_stream.read()
                    text = blob_data.decode('utf-8')
                    self._process_blob_text(text, file_path, commit_sha, commit_date, commit_msg)
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Error reading blob for {file_path} in {commit_sha}: {e}")

    def _process_blob_text(self, text: str, file_path: str, commit_sha: str, commit_date: str, commit_msg: str):
        # Always True for is_tracked since it's in git history
        self.orchestrator.scan_content(
            text, file_path, "git_history", is_tracked=True,
            commit_sha=commit_sha, commit_date=commit_date, commit_message=commit_msg
        )
