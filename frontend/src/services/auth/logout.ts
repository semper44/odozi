import { tokenStore } from "@/services/auth/tokenStore";

const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export async function logout(): Promise<void> {
  const response = await fetch(`${backendUrl}/account/api/auth/logout/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });

  tokenStore.clear();

  if (!response.ok && response.status !== 401 && response.status !== 403) {
    throw new Error("Could not log out. Please try again.");
  }
}
