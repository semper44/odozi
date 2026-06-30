from pydantic import BaseModel, Field
from typing import List, Optional

class RepositoryItem(BaseModel):
    repo_name: str = Field(description="Name of the repo (e.g., 'repo-a')")
    repo_owner: str = Field(default="unknown_owner")
    repo_full_name: str = Field(description="Formatted as owner/repo_name")
    target_branch: Optional[str] = Field(
        default=None, 
        description="The specific branch requested (e.g., 'main', 'staging'). Set to null or 'unknown' if not specified."
    )

class ToolStrategyMapping(BaseModel):
    strategy: str = Field(description="e.g., 'pytest', 'bandit', 'generate_django_tests'")
    target_repo_names: List[str] = Field(description="Target repos for this specific tool")
    target_branch: Optional[str] = Field(
        default=None, 
        description="The branch context requested for this tool execution run. Set to null if unprovided."
    )
class WorkspaceCreationTask(BaseModel):
    new_workspace_name: str = Field(description="The workspace name to create (e.g., 'mom')")
    repositories: List[str] = Field(description="List of repo names to put in this workspace")

class RepoExecutionRule(BaseModel):
    repo_name: str = Field(description="Name of the repository")
    target_branch: str = Field(default="master")
    strategies: List[str] = Field(description="List of security strategies to run, e.g., ['bandit', 'pii_leakage']")


class OrchestratorAction(BaseModel):
    """
    The Master Multitask Schema. Allows combinations of operations in 1 chat turn.
    """
    intents: List[str] = Field(
        description="List of all detected intents, e.g., ['create_workspace', 'run_static_analysis']"
    )

    evict_prior_history: bool = Field(
        default=False,
        description="Set to True ONLY when an execution command is given. This signals the backend to execute a complete database overhaul."
    )
    condensed_history_summary: Optional[str] = Field(
        None,
        description="When evict_prior_history is True, compile a high-utility, short summary of the important context and execution choices from the past casual turns to act as the lone seed for future memory."
    )
    
    ui_layout_route: str = Field(
        description="Select layout mode code. Must be: 'CHAT', 'CARD', or 'TERM'."
    )
    chat_response: str = Field(
        description="Your natural, friendly response explaining your actions and technical insights."
    )
    
    # 🌟 Multi-Workspace Tracking Array
    workspaces_to_create: List[WorkspaceCreationTask] = Field(
        default=[], 
        description="Populate this with an object for EVERY workspace the user wants to create."
    )
    
    # Execution Mappings
    # selected_repo_names: List[str] = Field(default=[], description="All repositories involved across the entire request")
      # 🌟 NEW STRUCTURE: A flat list of repositories and their tools
    active_rules: List[RepoExecutionRule] = Field(
        default=[],
        description="List of each repo and the specific strategies assigned to it."
    )
