// useStreamingSocket.ts
import { useEffect } from "react";
import { socketService } from "@/services/websocket/socket";
import type { StreamingMessage } from "./types";

export const useStreamingSocket = (onMessageReceived?: (data: any) => void) => {
  useEffect(() => {
    
    // Abstracted ticket retrieval handler
    const fetchNewTicket = async (): Promise<string | null> => {
      try {
        // credentials: "include" guarantees the browser sends HttpOnly cookies automatically
        const response = await fetch("http://127.0.0.1:8000/account/api/auth/ws-ticket/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include", 
        });

        if (response.status === 401) {
          console.error("👤 Authentication cookie invalid, expired, or missing.");
          return null; 
        }

        if (!response.ok) throw new Error("Pre-flight server error during flight generation");

        const data = await response.json();
        return data.ticket; // Returns the clean, randomized ticket identifier string
      } catch (err) {
        console.error("🚨 Network failure communicating with ticket provider view:", err);
        return null;
      }
    };

    // Inject configuration into our persistent cross-component Singleton service
    socketService.configure({
      baseUrl: "ws://127.0.0.1:8000/ws/chat/",
      fetchTicket: fetchNewTicket,
    });

    // Fire the initial activation step
    socketService.connect();

    if (onMessageReceived) {
      socketService.onMessage((data: StreamingMessage) => {
        onMessageReceived(data);
      });
    }

    return () => {
      // Retaining connection lifecycle active to prevent HMR disruptions in local development environments.
    };
  }, [onMessageReceived]);

  return {
    sendMessage: (message: string) => {
      socketService.send({ message });
    },
  };
};
