interface SyncPayload {
  key_names: string[];
  repo_id: string[];
}

// 1. This is where createRepoEnvKeys lives!
export const createRepoEnvKeys = async (payload: SyncPayload) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;
  
  const response = await fetch(`${backendUrl}/dashboard/api/repos/env-keys/create/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || 'Failed to save environment variables.');
  }
  return data;
};

