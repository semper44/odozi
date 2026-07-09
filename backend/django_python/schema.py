from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any



class RepositoryItem(BaseModel):
    """The master repository descriptor used across all execution rules and metadata tracks."""
    repo_id: Optional[int] = Field(default=None, description="The unique GitHub global repository integer ID")
    repo_name: str = Field(description="Name of the repo (e.g., 'Taskmaster')")
    repo_owner: str = Field(default="unknown_owner", description="The owner account username")
    repo_full_name: str = Field(description="Formatted as owner/repo_name")
    target_branch: Optional[str] = Field(
        default=None, 
        description="The specific branch requested (e.g., 'main'). Set to null if not specified."
    )


class RepoEnvKeyCreationTask(BaseModel):
    """Maps fields directly to your create_repo_env_keys_service function parameter footprint."""
    workspace_name: str = Field(
        default="default",
        description="The target workspace context. Set to 'default' if not specified."
    )
    key_names: List[str] = Field(
        description="List of environment key strings to inject (e.g., ['STRIPE_API_KEY', 'DB_PASSWORD'])"
    )
    selected_repo_ids: List[int] = Field(
        description="Array of target GitHub repo IDs where these keys must be mapped"
    )
    # 🌟 Cleaned up to use the shared master RepositoryItem class
    repositories_data: List[RepositoryItem] = Field(
        default=[],
        description="Full metadata objects list required to defensively instantiate missing database records"
    )


class RepoEnvKeyDeletionTask(BaseModel):
    """Maps fields directly to your delete_repo_env_keys_service function parameter footprint."""
    key_names: List[str] = Field(
        description="List of exact environment key variable names to bulk delete"
    )
    selected_repo_ids: List[int] = Field(
        description="Array of target GitHub repo IDs from which the keys will be stripped"
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


    """Captures explicit ID and metadata to execute your delete_workspace_with_repos function."""
    workspace_id: int = Field(description="The database primary key integer ID of the workspace to purge")
    workspace_name: str = Field(description="The name of the workspace being targeted for deletion")


class WorkspaceDeletionTask(BaseModel):
    """Captures explicit ID and metadata to execute your delete_workspace_with_repos function."""
    workspace_id: int = Field(description="The database primary key integer ID of the workspace to purge")
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
                """    )

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

    workspaces_to_delete: List[WorkspaceDeletionTask] = Field(
            default=[],
            description="Populate this with an object context for EVERY workspace the user wants to delete."
        )  
      
    env_keys_to_create: List[RepoEnvKeyCreationTask] = Field(
        default=[],
        description="Populate this for EVERY explicit request to register or add repository environment variable configs."
    )
    env_keys_to_delete: List[RepoEnvKeyDeletionTask] = Field(
        default=[],
        description="Populate this for EVERY explicit request to strip or purge repository environment keys."
    )

    # Execution Mappings
    # selected_repo_names: List[str] = Field(default=[], description="All repositories involved across the entire request")
      # 🌟 NEW STRUCTURE: A flat list of repositories and their tools
    active_rules: List[RepoExecutionRule] = Field(
        default=[],
        description="List of each repo and the specific strategies assigned to it."
    )


