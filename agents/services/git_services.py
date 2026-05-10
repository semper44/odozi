import os
import tempfile
import shutil
from git import Repo

class CIWorkspace:
    def __init__(self, repo_url, branch="main"):
        self.repo_url = repo_url
        self.branch = branch
        self.root_dir = None
        self.repo = None

    def __enter__(self):
        """Sets up the sandbox when using 'with CIWorkspace(...) as ws':"""
        self.root_dir = tempfile.mkdtemp(prefix="ci_agent_")
        print(f"--- Creating sandbox at: {self.root_dir} ---")
        self.repo = Repo.clone_from(self.repo_url, self.root_dir, branch=self.branch)
        return self

    def get_diff(self, base_branch="main"):
        """Gets the code changes compared to the base branch."""
        # This gives us the actual code changes (the 'patch')
        diff_index = self.repo.git.diff(base_branch, self.branch)
        return diff_index

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Automatically cleans up the sandbox folder when done."""
        if self.root_dir and os.path.exists(self.root_dir):
            shutil.rmtree(self.root_dir)
            print(f"--- Sandbox {self.root_dir} destroyed ---")

