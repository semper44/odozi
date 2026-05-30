import { useEffect } from "react";
import { socketService } from "@/services/websocket/socket";
import type { ChatMessage } from "./types";



export const useChatSocket = () => {
  useEffect(() => {
    socketService.connect("ws://localhost:8000/ws/chat/");

    socketService.onMessage((data: ChatMessage) => {
      console.log("Received:", data);
    });

    return () => {
      socketService.disconnect();
    };
  }, []);

  return {
    sendMessage: (message: string) => {
      socketService.send({
        message,
      });
    },
  };
};