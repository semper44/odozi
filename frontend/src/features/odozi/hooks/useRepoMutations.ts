import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSelectedRepos } from "../apis/createrepotest"; 
import {createRepoEnvKeys} from "../apis/CreateEnv"
import { toast } from 'react-toastify';


// Explicit type contract describing your database mapping structure
export interface GitHubRepoPayload {
  github_id: number;
  repo_name: string;
  repo_owner: string;
  repo_full_name: string;
}

// Inside useRepoMutations.ts:

export const useCreateReposMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    // Map object directly
    mutationFn: createSelectedRepos, 
    onSuccess: () => {
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



export const useCreateEnvKeysMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createRepoEnvKeys,
    onSuccess: (data) => {
      toast.success(data.message || "Environment keys saved successfully!");
      queryClient.invalidateQueries({ queryKey: ["env-keys"] });
    },
    onError: (err: any) => {
      toast.error(`❌ ${err.message}`);
    }
  });
};

// Append inside useRepoMutations.ts:
// export const createWorkspaceApi = async (name: string) => {
//   const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

//   const response = await fetch(`${backendUrl}/api/workspaces/create/`, {
//     method: "POST",
//     credentials: "include", // Essential for HttpOnly cookies parsing
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({ name }),
//   });

//   if (!response.ok) {
//     const err = await response.json().catch(() => ({}));
//     throw new Error(err.error || "Failed creating database workspace row.");
//   }
//   return response.json();
// };

// export const useCreateWorkspaceMutation = () => {
//   const queryClient = useQueryClient();

//   return useMutation({
//     mutationFn: (name: string) => createWorkspaceApi(name),
//     onSuccess: () => {
//       // Invalidate your main repo cache to instantly refresh dropdown components with the new workspace ID options
//       queryClient.invalidateQueries({ queryKey: ["repos"] });
//     },
//   });
// };
