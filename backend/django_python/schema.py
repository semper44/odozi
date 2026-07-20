from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any



class RepoEnvKeyCreationTask(BaseModel):
    """Maps fields directly to your create_repo_env_keys_service function parameter footprint."""
    workspace_name: str = Field(
        default="default",
        description="The target workspace context. Set to 'default' if not specified."
    )
    key_names: List[str] = Field(
        description="List of environment key strings to inject (e.g., ['STRIPE_API_KEY', 'DB_PASSWORD'])"
    )

    repositories: List[str] = Field(
        default=[],
        description="The name of the exact repository (e.g., 'Taskmaster')"
    )


class RepoEnvKeyDeletionTask(BaseModel):
    """Maps fields directly to your polymorphic delete_repo_env_keys_service function parameter footprint."""
    
    delete_which: str = Field(
        description="Must be strictly one of these structural scope targets: 'workspace', 'repo', or 'key_names'."
    )
    
    workspace_name: Optional[str] = Field(
        default=None,
        description="The name of the target workspace context. Required if delete_which is 'workspace'."
    )
    
    key_names: List[str] = Field(
        default=[],
        description="List of exact environment key variable names to bulk delete (e.g., ['DB', 'CLOUDFLARE'])."
    )
    
    repositories: List[str] = Field(
        default=[],
        description="The name of the exact repository (e.g., 'Taskmaster')"
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
    # Your fine-tuned flat string list remains 100% untouched!
    repositories: List[str] = Field(description="List of repo names to put in this workspace")


class WorkspaceDeletionTask(BaseModel):
    """Captures explicit ID and metadata to execute your delete_workspace_with_repos function."""
    # 🌟 Fixed: Changed from a strict required int to an optional int with a fallback default 0!
    workspace_name: str = Field(description="The name of the workspace being targeted for deletion")


class RepoExecutionRule(BaseModel):
    repo_name: str = Field(description="Name of the repository")
    target_branch: str = Field(default="master")
    strategies: Dict[str, Dict[str, Any]] = Field(
        default={},
        description="""
        A dictionary mapping the tool strategy name to its parameters.
        Example: 
        {
        "check_transaction_atomic": {"target": {}, "constraints": {"must_call": "atomic"}},
        "bandit": {}
        }
        """
    )

class OrchestratorAction(BaseModel):
    """
    The Master Multitask Schema. Allows combinations of operations in 1 chat turn.
    """
    intents: List[str] = Field(
        description="""
        Detected intents. Options: ['create_workspace', 'delete_workspace', 
        'create_repo_env', 'delete_repo_env', 'run_static_analysis']
        """
    )
    evict_prior_history: bool = Field(
        default=False,
        description="Set to True ONLY when an execution command is given."
    )
    condensed_history_summary: Optional[str] = Field(
        None,
        description="When evict_prior_history is True, compile a high-utility context summary."
    )
    ui_layout_route: str = Field(
        description="Select layout mode code. Must be: 'CHAT', 'CARD', or 'TERM'."
    )
    chat_response: str = Field(
        description="Your natural, friendly response explaining your actions and technical insights."
    )
    workspaces_to_create: List[WorkspaceCreationTask] = Field(default=[])
    workspaces_to_delete: List[WorkspaceDeletionTask] = Field(default=[])  
    env_keys_to_create: List[RepoEnvKeyCreationTask] = Field(default=[])
    env_keys_to_delete: List[RepoEnvKeyDeletionTask] = Field(default=[])
    active_rules: List[RepoExecutionRule] = Field(default=[])

