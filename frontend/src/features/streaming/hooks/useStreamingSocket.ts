// useStreamingSocket.ts
import { useEffect } from "react";
import { socketService } from "@/services/websocket/socket";

export const useStreamingSocket = (onMessageReceived?: (data: any) => void) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;
  const wsUrl = backendUrl.replace(/^http/, "ws");

  useEffect(() => {
    socketService.configure({
      baseUrl: `${wsUrl}/ws/chat/`,
    });

    socketService.connect();

    if (onMessageReceived) {
      socketService.onMessage((data) => {
        onMessageReceived(data);
      });
    }

    return () => {};
  }, [onMessageReceived]);

  // ✅ ADDED BACK: Expose the message sender helper function to your dashboard layout
  return {
    sendMessage: (payload: { type: string; repos: string[]; prompt: string }) => {
      socketService.send(payload);
    },
  };
};
