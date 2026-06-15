# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Orchestrator(BaseModel):
    intent: str = Field(description="Must be one of: 'run_static_analysis', 'create_workspace', or 'create_env_keys'")
    workspace_name: Optional[str] = Field(None, description="The extracted workspace name if applicable")
    target_repo_ids: List[str] = Field(default=[], description="List of stringified repository IDs mentioned")
    variables: List[str] = Field(default=[], description="Upper-case SNAKE_CASE configuration key names extracted")




class RepoMeta(BaseModel):
    branch: str = Field(default="main", description="Target git branch")
    base_branch: str = Field(default="main", description="Base git branch")

class ActiveRule(BaseModel):
    strategy: str = Field(description="Exact strategy name from registry (e.g., 'check_auth')")
    params: Dict[str, str] = Field(default={}, description="Key-value parameter pairs for the strategy")

class RepositoryItem(BaseModel):
    repo_id: int = Field(description="The unique GitHub resource ID integer")
    repo_name: str = Field(description="Individual repository name")
    repo_owner: str = Field(description="Organization or user owner name")
    repo_full_name: str = Field(description="Formatted strictly as 'owner/repo_name'")

class OrchestratorAction(BaseModel):
    """
    The Master Root Schema. LangChain forces the LLM to output this exact structure.
    """
    intent: str = Field(
        description="Must be exactly one of: 'run_static_analysis', 'create_workspace', or 'create_env_keys'"
    )
    
    # Fields for 'run_static_analysis'
    repo_meta: Optional[RepoMeta] = Field(None)
    environment_variables: Dict[str, str] = Field(default={})
    active_rules: List[ActiveRule] = Field(default=[])
    
    # Fields for 'create_workspace'
    new_workspace_name: Optional[str] = Field(None)
    
    # Shared fields for workspace & env configurations
    workspace: Optional[str] = Field(None, description="Target workspace name")
    key_names: List[str] = Field(default=[], description="Upper-case SNAKE_CASE variable keys")
    selected: List[str] = Field(default=[], description="Stringified repository ID selection targets")
    repositories: List[RepositoryItem] = Field(default=[])
