// socket.ts
import type { StreamingMessage } from "./types";

interface SocketConfig {
  baseUrl: string;
}

class SocketService {
  private socket: WebSocket | null = null;
  private messageCallback: ((data: StreamingMessage) => void) | null = null;
  private config: SocketConfig | null = null;
  private isIntentionalDisconnect: boolean = false;
  private reconnectTimeoutId: any = null;
  private currentDelay: number = 1000; // Base backoff delay (1s)
  private maxDelay: number = 16000;    // Cap backoff delay (16s)

  public configure(config: SocketConfig) {
    this.config = config;
  }

  async connect() {
    if (!this.config) {
      console.error("🚨 SocketService initialized without a structural configuration.");
      return;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return; // Absolute safety lock avoiding connection duplicate storms
    }

    this.isIntentionalDisconnect = false;
    
    // ✅ FIX: Clean, generic WebSocket path deployment. 
    // The browser automatically packages your HttpOnly auth cookies into this connection flight!
    const cleanUrl = this.config.baseUrl;
    this.socket = new WebSocket(cleanUrl);

    this.socket.onopen = () => {
      console.log("⚡ Browser WebSocket Channel Established via Secure HttpOnly Cookie");
      this.currentDelay = 1000; // Reset exponential sequence backoff upon clean entry
    };

    this.socket.onclose = (event) => {
      this.socket = null;
      
      if (event.code === 4001) {
        console.error("🚨 Connection rejected: Login session invalid or unauthenticated.");
        // Stop retrying if the user session is completely dead
        return;
      }

      if (!this.isIntentionalDisconnect) {
        console.warn(`❌ Unscheduled link failure (Code: ${event.code}). Launching reconnect script...`);
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = (error) => {
      console.error("🚨 Core browser connection layer error detected:", error);
    };

    this.socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (this.messageCallback) {
          this.messageCallback(parsed);
        }
      } catch (err) {
        console.error("⚠️ Failed parsing incoming WebSocket JSON data frame payload:", err);
      }
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimeoutId) return; // Guard against overlapping duplicate timers

    this.reconnectTimeoutId = setTimeout(async () => {
      this.reconnectTimeoutId = null;
      await this.connect();
    }, this.currentDelay);

    // Progressive Jittered Exponential Backoff sequence calculation
    this.currentDelay = Math.min(this.currentDelay * 2, this.maxDelay);
  }

  send(data: any) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    } else {
      console.warn("⚠️ Transaction aborted: Network pipeline connection closed.");
    }
  }

  onMessage(callback: (data: StreamingMessage) => void) {
    this.messageCallback = callback;
  }

  disconnect() {
    this.isIntentionalDisconnect = true;
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.messageCallback = null;
  }
}

export const socketService = new SocketService();
