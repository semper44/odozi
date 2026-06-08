// @/features/repositories/hooks/useRepoMutations.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSelectedRepos } from "../apis/createrepotest"; // Adjust relative path

// Explicit type contract describing your database mapping structure
export interface GitHubRepoPayload {
  github_id: number;
  repo_name: string;
  repo_owner: string;
  repo_full_name: string;
}

// 1. Hook wrapper handling high-speed bulk database creations
export const useCreateReposMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ workspaceId, repos }: { workspaceId: string | number; repos: GitHubRepoPayload[] }) => 
      createSelectedRepos(workspaceId, repos),
    onSuccess: (data) => {
      console.log(`🎉 Connected ${data.saved_count} new repository pipelines!`);
      // Invalidate the 'repos' cache key to force a fresh data sync
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
};

// 2. Hook wrapper handling high-speed bulk database deletions
export const useDeleteReposMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repoIds: number[]) => deleteSelectedRepos(repoIds),
    onSuccess: () => {
      console.log("🔥 Successfully wiped repository selections from database.");
      // Invalidate the 'repos' cache key to clear out the disconnected UI cards
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
};


// Append inside useRepoMutations.ts:
export const createWorkspaceApi = async (name: string) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

  const response = await fetch(`${backendUrl}/api/workspaces/create/`, {
    method: "POST",
    credentials: "include", // Essential for HttpOnly cookies parsing
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error || "Failed creating database workspace row.");
  }
  return response.json();
};

export const useCreateWorkspaceMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) => createWorkspaceApi(name),
    onSuccess: () => {
      // Invalidate your main repo cache to instantly refresh dropdown components with the new workspace ID options
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
};
