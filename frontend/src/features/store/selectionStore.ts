import { create } from "zustand";
import { persist } from 'zustand/middleware';
import { toast } from 'react-toastify';


interface SelectionStore {
  selected: Set<string>;

  toggleSelect: (id: string) => void;

  clearSelection: () => void;

  selectAll: (ids: string[]) => void;
}

interface LLMState {
  /** The currently selected LLM provider, e.g. "gemini" or "openai". */
  activeProvider: string;

  /** The currently selected model for the active provider. 'gpt-4o', 'gpt-4o-mini' */
  activeModel: string;

  /** Updates the active LLM provider and model. */
  setLLMConfig: (provider: string, model: string) => void;
}


interface SocketState {
  isConnected: boolean;
  isProcessing: boolean;
  statusMessage: string;
  socketError: SocketErrorPayload | null;
   activeToast: string | null;
  streamingMessage: any | null;  // Global streaming data
  
  // Actions to mutate state from my WebSocket manager
  setConnectionStatus: (status: boolean) => void;
  setProcessingStatus: (isProcessing: boolean, message?: string) => void;
  setSocketError: (message: string, isImportant?: boolean) => void;
  triggerToastNotification: (message: string) => void;
  setStreamingMessage: (data: any) => void;  // Action to update streaming data
  clearSocketStatus: () => void;
}

interface SocketErrorPayload {
  message: string;
  isImportant: boolean;
}



export const useSelectionStore =
  create<SelectionStore>((set) => ({
    selected: new Set(),

    toggleSelect: (id) =>
      set((state) => {
        const next = new Set(state.selected);

        if(next.has(id)) {
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





export const useSocketStore = create<SocketState>((set) => ({
  isConnected: false,
  isProcessing: false,
  statusMessage: '',
  socketError: null,
  activeToast: null,
  streamingMessage: null,  //Initialize streaming data
  

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

  triggerToastNotification: (message: string) => {
    const trimmed = message?.trim();
    set({ activeToast: trimmed || null });
    // Display my toast notification immediately whenever an active message is triggered
    if(trimmed){
      toast.error(trimmed, {
        position: "top-right",
        autoClose: 4000,
        theme: "colored",
      });
    }
  },
  
  setStreamingMessage: (data) => set({ streamingMessage: data }),  //Action to set streaming data
  
  clearActiveToast: () => set({ activeToast: null })
}));
