import { useQuery } from "@tanstack/react-query";
import {
  fetchRepos,
  type Repository,
  type FetchReposResponse,
} from "../api/githubApi";

export interface EnrichedRepository extends Repository {
  workspaceName: string;
  hasWorkspace: boolean;
}

export interface ReposQueryData
  extends Omit<FetchReposResponse, "repositories"> {
  repositories: EnrichedRepository[];
  uniqueWorkspaces: string[];
}

export const useRepos = () => {
  return useQuery<FetchReposResponse, Error, ReposQueryData>({
    queryKey: ["repos"],
    queryFn: fetchRepos,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: false,

    select: (rawResponseData) => {
      const {
        repositories = [],
        repo_selection = [],
      } = rawResponseData;

      const selectionMap = new Map<number, string>();
      const workspaceNamesSet = new Set<string>();

      repo_selection.forEach((item) => {
        if (item.repo_id) {
          const wsName = item.workspace__name || "";

          selectionMap.set(item.repo_id, wsName);

          if (wsName) {
            workspaceNamesSet.add(wsName);
          }
        }
      });

      const enrichedRepositories: EnrichedRepository[] =
        repositories.map((repo) => ({
          ...repo,
          workspaceName: selectionMap.get(Number(repo.id)) || "",
          hasWorkspace: selectionMap.has(Number(repo.id)),
        }));

      return {
        ...rawResponseData,
        repositories: enrichedRepositories,
        uniqueWorkspaces: Array.from(workspaceNamesSet),
      };
    },
  });
};