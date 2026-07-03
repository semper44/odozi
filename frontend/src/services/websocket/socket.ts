// socket.ts
import type { StreamingMessage } from "./types";
import { useSocketStore } from "@/features/store/selectionStore"
import { toast } from 'react-toastify';

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
  private count: number = 0; 
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
      this.count=0
      this.currentDelay = 1000; // Reset exponential sequence backoff upon clean entry
      useSocketStore.getState().setConnectionStatus(true);
      useSocketStore.getState().setSocketError(null);
      useSocketStore.getState().triggerToastNotification(null);

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
        useSocketStore.getState().setSocketError("Gateway terminated connection: Reconnecting")
        if (this.count < 1) {
          useSocketStore.getState().triggerToastNotification("❌ Connection dropped. Reconnecting to gateway...");
        }
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = (error) => {
      console.error(this.count, "🚨 Core browser connection layer error detected:", error);
      if (this.count < 1) {
        useSocketStore.getState().triggerToastNotification("❌ Network handshake verification failure.");
      }
      useSocketStore.getState().setSocketError("Network handshake verification failure.")
    };

    this.socket.onmessage = (event) => {
      try {
        const packet = JSON.parse(event.data);
        console.log("📥 Raw Network Packet Received:", packet);

        if (packet.type === "status") {
          // to output different stages of the llm chat and Test, whether its connecting to github or running pytest, etc
          useSocketStore.getState().setProcessingStatus(true, packet.message || "Processing...");
        } 

        else if (packet.type === "error") {
          useSocketStore.getState().setProcessingStatus(false); // Stop loading 
          console.log("eche", packet);

          let displayMessage = packet.message;

          if (typeof displayMessage === "string") {
            const lowerMessage = displayMessage.toLowerCase();
            
            // Catch-all keywords for Gemini, OpenAI, and Anthropic quota/rate errors
            const isQuotaError = 
              lowerMessage.includes("resource_exhausted") || 
              lowerMessage.includes("insufficient_quota") || 
              lowerMessage.includes("rate_limit") || 
              lowerMessage.includes("exceeded your current quota");

            if (isQuotaError) {
              displayMessage = "⚠️ You have exceeded your LLM API daily quota limit. Please try again tomorrow or upgrade your plan.";
            }
          }
          console.log(displayMessage, "🎯 Chat message:");

          useSocketStore.getState().setSocketError(displayMessage);
            console.log("🟢 STEP 2: Zustand global store has been set to:", useSocketStore.getState().socketError)
        }

        else if (packet.type === "orchestration_result") {
          useSocketStore.getState().setProcessingStatus(false);

          let cleanPayload = packet;

          // 🌟 SENIOR FIX: If the engine wraps the output as a stringified string, unpack it here
          if (packet.raw_output && typeof packet.raw_output === "string") {
            try {
              cleanPayload = JSON.parse(packet.raw_output);
            } catch (parseErr) {
              console.error("🚨 Failed unpacking nested raw_output string payload frame:", parseErr);
            }
          }

          // ✅ Dispatch to global store so ANY component can access it
          useSocketStore.getState().setStreamingMessage(cleanPayload);
          
          // ✅ Also fire callback if listener exists (for backward compatibility)
          if (this.messageCallback) {
            this.messageCallback(cleanPayload);
          }
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

    // 🟡 Reset state tracking variables upon disconnect execution
    useSocketStore.getState().setConnectionStatus(false);
    useSocketStore.getState().clearSocketStatus();
  }

  
}

export const socketService = new SocketService();