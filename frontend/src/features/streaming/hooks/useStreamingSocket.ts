import { useEffect, useRef } from "react";
import { socketService } from "@/services/websocket/socket";


interface StreamingSocketPayload {
    type: string;
    prompt: string;
    provider?: string;
    model_name?: string;
    repos?: string[];
}

export const useStreamingSocket = (onMessageReceived?: (data: any) => void) => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;
  const wsUrl = backendUrl.replace(/^http/, "ws");
  const onMessageRef = useRef(onMessageReceived);
  onMessageRef.current = onMessageReceived;

  useEffect(() => {
    socketService.configure({
      baseUrl: `${wsUrl}/ws/chat/`,
    });

    socketService.connect();

    socketService.onMessage((data) => {
      onMessageRef.current?.(data);
    });

    return () => {};
  }, [wsUrl]);

  // Exposing my message sender helper function to my dashboard layout
  return {
      sendMessage: (payload: StreamingSocketPayload) => {
          socketService.send(payload);
      },
  };
};
