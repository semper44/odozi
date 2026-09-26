const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export const fetchChatSession = async (sessionId: number) => {
  const response = await fetch(
    `${backendUrl}/general/api/chat-history/${sessionId}/`,
    {
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw new Error("Unable to load chat session");
  }

  return response.json();
};