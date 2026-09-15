// socket.ts
import { useSocketStore } from "@/features/store/selectionStore"

// interface SocketConfig {
//   baseUrl: string;
// }

class SocketService {
  private socket: WebSocket | null = null;
  private messageCallback: ((data: any) => void) | null = null;
  private config: any | null = null;
  private isIntentionalDisconnect: boolean = false;
  private reconnectTimeoutId: any = null;
  private currentDelay: number = 1000; 
  private hasFiredErrorThisSession: boolean = false; // 🌟 NEW STATE: Explicit tracking toggle
  private maxDelay: number = 16000;    

  public configure(config: any) {
    this.config = config;
  }

  async connect() {
    if (!this.config) {
      console.error("🚨 SocketService initialized without a structural configuration.");
      return;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return; 
    }

    this.isIntentionalDisconnect = false;
    const cleanUrl = this.config.baseUrl;
    this.socket = new WebSocket(cleanUrl);

    this.socket.onopen = () => {
      console.log("⚡ Browser WebSocket Channel Established via Secure HttpOnly Cookie");
      
      // 🌟 Clean session flags cleanly upon successful connection entry
      this.hasFiredErrorThisSession = false;
      this.currentDelay = 1000; 
      
      useSocketStore.getState().setConnectionStatus(true);
      useSocketStore.getState().triggerToastNotification(null);
      useSocketStore.getState().clearSocketStatus(); 
    };

    this.socket.onclose = (event) => {
      if (event.code === 4001) {
        console.error("🚨 Connection rejected: Login session invalid or unauthenticated.");
        return;
      }

      if (!this.isIntentionalDisconnect) {
        console.warn(`❌ Unscheduled link failure (Code: ${event.code}). Launching reconnect script...`);
        
        // 🌟 Use our new boolean flag to guarantee the notification fires EXACTLY ONCE per drop
        if (!this.hasFiredErrorThisSession) {
          useSocketStore.getState().setSocketError("Gateway terminated connection: Reconnecting", false);
          useSocketStore.getState().triggerToastNotification("❌ Connection dropped. Reconnecting to gateway...");
          this.hasFiredErrorThisSession = true; // Lock execution
        }
        
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = (error) => {
      console.error("🚨 Core browser connection layer error detected:", error);
      
      // 🌟 Lock out duplicate noise: Only notify the interface once per connection break session
      if (!this.hasFiredErrorThisSession) {
        useSocketStore.getState().triggerToastNotification("❌ Please login again.");
        useSocketStore.getState().setSocketError("Please login again.", false);
        this.hasFiredErrorThisSession = true; 
      }
    };

    this.socket.onmessage = (event) => {
      try {
        const packet = JSON.parse(event.data);
        console.log("📥 Raw Network Packet Received:", packet);

        if (packet.type === "status") {
          useSocketStore.getState().setProcessingStatus(true, packet.message || "Processing...");
        } 

        else if (packet.type === "error") {
          useSocketStore.getState().setProcessingStatus(false); 
          console.log("eche", packet);

          let displayMessage = packet.message;

          if (typeof displayMessage === "string") {
            const lowerMessage = displayMessage.toLowerCase();
            
            // 🌟 Handles Celery auto-retry log output safely
            if (lowerMessage.includes("unexpected_eof_while_reading") || lowerMessage.includes("eof occurred")) {
              displayMessage = 'Network error, please check your internet connection and try again, Or the LLM provider is taking too long to respond.';
            }
            
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
          
          // 🌟 This triggers your main modal alert securely on the React layout canvas
          useSocketStore.getState().setSocketError(displayMessage, true);
        }

        else if (packet.type === "orchestration_result") {
          useSocketStore.getState().setProcessingStatus(true);
          let cleanPayload = packet;

          if (packet.raw_output && typeof packet.raw_output === "string") {
            try {
              cleanPayload = JSON.parse(packet.raw_output);
            } catch (parseErr) {
              console.error("🚨 Failed unpacking nested raw_output string payload frame:", parseErr);
            }
          }

          console.log("dripppp", cleanPayload)

          useSocketStore.getState().setStreamingMessage(cleanPayload);
          
          if (this.messageCallback) {
            this.messageCallback(cleanPayload);
          }
        }

        else if (packet.type === "follow_up_result") {
          // 🎯 Turn off your processing loading animations across the React application canvas
          useSocketStore.getState().setProcessingStatus(false);
          
          let cleanFollowUpPayload = packet;

          // Safely unpack the nested stringified JSON block from your Celery follow-up task
          if(packet.raw_output) {
            if (typeof packet.raw_output === "string") {
              try {
                cleanFollowUpPayload = JSON.parse(packet.raw_output);
              } catch (parseErr) {
                console.error("🚨 Failed unpacking nested follow_up raw_output payload:", parseErr);
              }
            } 
          }

          console.log("🎯 Unpacked Follow-up Payload:", cleanFollowUpPayload);

          // Updating my chat messaging streams so the user sees the explanation question
          useSocketStore.getState().setStreamingMessage(cleanFollowUpPayload);
          
          if (this.messageCallback) {
            this.messageCallback(cleanFollowUpPayload);
          }
        }

      } catch (err) {
        console.error("⚠️ Failed parsing incoming WebSocket JSON data frame payload:", err);
      }
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimeoutId) return; 

    this.reconnectTimeoutId = setTimeout(async () => {
      this.reconnectTimeoutId = null;
      await this.connect();
    }, this.currentDelay);

    this.currentDelay = Math.min(this.currentDelay * 2, this.maxDelay);
  }

  send(data: any) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    } else {
      console.warn("⚠️ Transaction aborted: Network pipeline connection closed.");
    }
  }

  onMessage(callback: (data: any) => void) {
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

    useSocketStore.getState().setConnectionStatus(false);
    useSocketStore.getState().clearSocketStatus();
  }
}

export const socketService = new SocketService();