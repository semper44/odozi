// Repository returned by Django inside "repositories"
export interface Repository {
  id: number;
  name: string;
  full_name: string;
  default_branch: string;
}

// Existing repo_selection data can contain additional fields,
// so we don't need to guess every backend field yet.
export interface RepoSelection {
  repo_id: number;
  workspace__name?: string;
  [key: string]: unknown;
}

export interface LLMConfigInterface {
  /** The LLM provider, e.g. "gemini", "openai", or "anthropic". */
  provider: string;

  /** The model name used by the selected provider. */
  model_name: string;
}

export interface FetchReposResponse {
  repositories: Repository[];
  repo_selection: RepoSelection[];
  my_jwt_access_token: string;
  installed_github: boolean;
  my_jwt_access_refresh: string;
  username: string;
  user_id: number | string;
  expires_at: string;
  llm_config: LLMConfigInterface
}

export const fetchRepos = async (): Promise<FetchReposResponse> => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

  const response = await fetch(`${backendUrl}/dashboard/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    let errorDetails = "Unknown API Error";

    try {
      const errorJson = await response.json();
      errorDetails = errorJson.error || errorDetails;
    } catch {
      errorDetails = response.statusText;
    }

    const apiError = new Error(errorDetails);

    // Preserve the HTTP status without using `any`.
    Object.assign(apiError, {
      status: response.status,
    });

    throw apiError;
  }

  return response.json() as Promise<FetchReposResponse>;
};