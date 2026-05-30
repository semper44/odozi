import { useEffect } from "react";
import { socketService } from "@/services/websocket/socket";
import type { StreamingMessage } from "./types";



export const useStreamingSocket = () => {
  useEffect(() => {
    socketService.connect("ws://localhost:8000/ws/chat/");

    socketService.onMessage((data: StreamingMessage) => {
      console.log("Received:", data);
    });

    return () => {
      // socketService.disconnect();
    };
  }, []);

  return {
    sendMessage: (message: string) => {
      socketService.send({
        message,
      });
      console.log("chatmessae", message)
    },
  };
};