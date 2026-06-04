import { useQuery } from "@tanstack/react-query";

import { fetchRepos } from "../api/githubApi";

export const useRepos = () => {
  return useQuery({
    queryKey: ["repos"],

    queryFn: fetchRepos,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: false,
  });
};