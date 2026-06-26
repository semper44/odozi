from pydantic import BaseModel, Field
from typing import List, Optional

class RepositoryItem(BaseModel):
    repo_name: str = Field(description="Name of the repo (e.g., 'repo-a')")
    repo_owner: str = Field(default="unknown_owner")
    repo_full_name: str = Field(description="Formatted as owner/repo_name")

class ToolStrategyMapping(BaseModel):
    strategy: str = Field(description="e.g., 'pytest', 'bandit', 'generate_django_tests'")
    target_repo_names: List[str] = Field(description="Target repos for this specific tool")

class WorkspaceCreationTask(BaseModel):
    new_workspace_name: str = Field(description="The workspace name to create (e.g., 'mom')")
    associated_repo_names: List[str] = Field(description="List of repo names to put in this workspace")

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
    active_rules: List[ToolStrategyMapping] = Field(
        default=[], 
        description="List mapping test runners or test generation tasks to specific repositories"
    )
