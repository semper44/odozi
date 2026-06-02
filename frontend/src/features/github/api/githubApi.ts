export const fetchRepos = async () => {
  const response = await fetch(
    "http://127.0.0.1:8000/api/github/repos/"
  );

  if (!response.ok) {
    throw new Error("Failed to fetch repos");
  }

  return response.json();
};