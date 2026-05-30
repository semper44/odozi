// socket.ts
import type { StreamingMessage } from "./types";

class SocketService {
  private socket: WebSocket | null = null;
  private messageCallback: ((data: StreamingMessage) => void) | null = null;

  connect(url: string) {
     console.log("CONNECTED INSTANCE");
      if (
        this.socket &&
        this.socket.readyState === WebSocket.OPEN
      ) {
        return;
      } // Prevent duplicate connections

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log("⚡ Browser WebSocket Connected Successfully", this);
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
    console.log("SEND INSTANCE", this);
    console.log("SOCKET", this.socket);
    console.log("READY STATE", this.socket?.readyState);
    if (this.socket?.readyState === WebSocket.OPEN) {
      console.log("ACTUALLY SENDING"); 
      this.socket.send(JSON.stringify(data));
      console.log("hmmmm"); 
    } else {
      console.warn("⚠️ Cannot send message: Socket is not open yet.");
    }
  }

  onMessage(callback: (data: StreamingMessage) => void) {
    this.messageCallback = callback; // Safely register callback anytime
  }

  disconnect() {
    this.socket?.close();
    this.socket = null;
    this.messageCallback = null;
  }
}

export const socketService = new SocketService();
