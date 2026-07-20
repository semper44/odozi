import { create } from "zustand";
import { persist } from 'zustand/middleware';


interface SelectionStore {
  selected: Set<string>;

  toggleSelect: (id: string) => void;

  clearSelection: () => void;

  selectAll: (ids: string[]) => void;
}

interface LLMState {
  activeProvider: string;
  activeModel: string;
  setLLMConfig: (provider: string, model: string) => void;
}


export const useSelectionStore =
  create<SelectionStore>((set) => ({
    selected: new Set(),

    toggleSelect: (id) =>
      set((state) => {
        const next = new Set(state.selected);

        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }

        return { selected: next };
      }),

    clearSelection: () =>
      set({
        selected: new Set(),
      }),

    selectAll: (ids) =>
      set({
        selected: new Set(ids),
      }),
      
  }));
  


export const useLLMStore = create<LLMState>()(
  persist(
    (set) => ({
      activeProvider: '',       
      activeModel: '',
      setLLMConfig: (provider, model) => 
        set({ activeProvider: provider, activeModel: model }),
    }),
    { name: 'odozi-llm-context' }
  )
);

interface SocketErrorPayload {
  message: string;
  isImportant: boolean;
}

interface SocketState {
  isConnected: boolean;
  isProcessing: boolean;
  statusMessage: string;
  socketError: SocketErrorPayload | null;
   activeToast: string | null;
  streamingMessage: any | null;  // ✅ Global streaming data
  
  // Actions to mutate state from your WebSocket manager
  setConnectionStatus: (status: boolean) => void;
  setProcessingStatus: (isProcessing: boolean, message?: string) => void;
  setSocketError: (message: string, isImportant?: boolean) => void;
  triggerToastNotification: (message: string) => void;
  setStreamingMessage: (data: any) => void;  // ✅ Action to update streaming data
  clearSocketStatus: () => void;
}

export const useSocketStore = create<SocketState>((set) => ({
  isConnected: false,
  isProcessing: false,
  statusMessage: '',
  socketError: null,
  activeToast: null,
  streamingMessage: null,  // ✅ Initialize streaming data
  

  setConnectionStatus: (status) => set({ isConnected: status }),
  
  setProcessingStatus: (isProcessing, message = '') =>
    set({ isProcessing, statusMessage: message }),

  setSocketError: (message, isImportant = false) => 
    set({ 
      socketError: { message, isImportant }, 
      isProcessing: false, 
      statusMessage: '' 
    }),
    
  clearSocketStatus: () => set({ isProcessing: false, statusMessage: '', socketError: null }),

  triggerToastNotification: (message) => set({ activeToast: message }),
  
  setStreamingMessage: (data) => set({ streamingMessage: data }),  // ✅ Action to set streaming data
  
  clearActiveToast: () => set({ activeToast: null })
}));
