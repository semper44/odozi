interface GitHubRepoPayload {
  github_id: number;
  repo_name: string;
  repo_owner: string;
  repo_full_name: string;
}

export const createSelectedRepos = async (payload: {
  workspaceId: number | null;
  newWorkspaceName: string | null;
  repositories: any[];
}) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;
  console.log("sea", `${backendUrl}/dasboard/api/workspaces/repos/create/`)

  const response = await fetch(`${backendUrl}/dashboard/api/workspaces/repos/create/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      new_workspace_name: payload.newWorkspaceName,
      repositories: payload.repositories,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error || "Failed executing pipeline creation mapping.");
  }
  return response.json();
};
