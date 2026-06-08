interface GitHubRepoPayload {
  github_id: number;
  repo_name: string;
  repo_owner: string;
  repo_full_name: string;
}

export const createSelectedRepos = async (workspaceId: string | number, repositories: GitHubRepoPayload[]) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

  const response = await fetch(`${backendUrl}/api/repos/create/`, { // Ensure path matches your urls.py
    method: "POST",
    credentials: "include", // 👈 CRITICAL: Transmits HttpOnly authentication cookies
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      workspace_id: workspaceId,
      repositories: repositories, // Array of dictionary payloads matching serializer schemas
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Bulk connection failed with status: ${response.status}`);
  }

  return response.json();
};
