from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class RepositoryItem(BaseModel):
    repo_name: str = Field(description="The extracted name of the repository (e.g., 'odozi')")
    repo_owner: str = Field(default="unknown_owner", description="The organization or user owner name if mentioned")
    repo_full_name: str = Field(description="Formatted strictly as 'owner/repo_name'")

class ToolStrategyMapping(BaseModel):
    strategy: str = Field(description="Exact tool strategy name from the registry (e.g., 'pytest' or 'bandit')")
    target_repo_names: List[str] = Field(description="The specific repository names this specific tool rule applies to")

class OrchestratorAction(BaseModel):
    """
    The Master Agent Schema. LangChain forces the LLM to output this exact structure.
    """
    intent: str = Field(
        description=(
            "Must be exactly one of: "
            "'create_workspace', 'delete_workspace', "
            "'create_env_keys', 'delete_env_keys', "
            "'general_chat', 'analyze_test_failure'"
        )
    )
    
    # 🌟 THE CONVERSATIONAL CORE FIELD
    # This is where the LLM writes its natural text, technical explanations, or hello messages!
    chat_response: Optional[str] = Field(
        None, 
        description="Write your natural text response, greetings, or deep technical analysis reports here."
    )
    
    # --- CREATION & DELETION CONFIGURATION FIELDS ---
    workspace: Optional[str] = Field(None, description="Target workspace container name involved in the action")
    new_workspace_name: Optional[str] = Field(None, description="Cleaned destination workspace name if creating one")
    
    key_names: List[str] = Field(
        default=[], 
        description="Upper-case SNAKE_CASE variable keys being added or deleted"
    )
    selected_repo_names: List[str] = Field(
        default=[], 
        description="Repository names involved in this specific pipeline turn"
    )
    
    repositories: List[RepositoryItem] = Field(
        default=[], 
        description="List of raw repository objects extracted if creating a workspace"
    )
    active_rules: List[ToolStrategyMapping] = Field(
        default=[], 
        description="List mapping specific tools to specific target repositories for analysis runs"
    )
