// socket.ts
import type { ChatMessage } from "./types";

class SocketService {
  private socket: WebSocket | null = null;
  private messageCallback: ((data: ChatMessage) => void) | null = null;

  connect(url: string) {
    if (this.socket) return; // Prevent duplicate connections

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log("⚡ Browser WebSocket Connected Successfully");
    };

    this.socket.onclose = () => {
      console.log("❌ Browser WebSocket Disconnected");
      this.socket = null; 
    };

    this.socket.onerror = (error) => {
      console.error("🚨 Browser WebSocket Error:", error);
    };

    // Centralized listener that delegates data to your active callback
    this.socket.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      if (this.messageCallback) {
        this.messageCallback(parsed);
      }
    };
  }

  send(data: any) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    } else {
      console.warn("⚠️ Cannot send message: Socket is not open yet.");
    }
  }

  onMessage(callback: (data: ChatMessage) => void) {
    this.messageCallback = callback; // Safely register callback anytime
  }

  disconnect() {
    this.socket?.close();
    this.socket = null;
    this.messageCallback = null;
  }
}

export const socketService = new SocketService();
