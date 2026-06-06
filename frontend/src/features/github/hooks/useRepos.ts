// useRepos.ts
import { useQuery } from "@tanstack/react-query";
import { fetchRepos } from "../api/githubApi";

export const useRepos = () => {
  return useQuery({
    queryKey: ["repos"],
    queryFn: fetchRepos,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: false,
    
    select: (rawResponseData) => {
      if (!rawResponseData) return { repositories: [], uniqueWorkspaces: [], username: "" };

      const { repositories = [], repo_selection = [] } = rawResponseData;

      // 1. Map workspace assignments
      const selectionMap = new Map<number, string>();
      const workspaceNamesSet = new Set<string>();

      repo_selection.forEach((item: any) => {
        if (item.repo_id) {
          const wsName = item.workspace__name || "";
          selectionMap.set(item.repo_id, wsName);
          if (wsName) workspaceNamesSet.add(wsName); // Collect unique names
        }
      });

      const enrichedRepositories = repositories.map((repo: any) => ({
        ...repo,
        workspaceName: selectionMap.get(repo.id) || "",
        hasWorkspace: selectionMap.has(repo.id),
      }));

      return {
        ...rawResponseData,
        repositories: enrichedRepositories,
        // Converting Set to an array list for the dropdown menu
        uniqueWorkspaces: Array.from(workspaceNamesSet), 
      };
    },
  });
};
