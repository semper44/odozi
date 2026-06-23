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
  savedApiKey: string;
  setLLMConfig: (provider: string, model: string, apiKey: string) => void;
}

interface SocketState {
  isConnected: boolean;
  isProcessing: boolean;
  statusMessage: string;
  socketError: string | null;
   activeToast: string | null;
  
  // Actions to mutate state from your WebSocket manager
  setConnectionStatus: (status: boolean) => void;
  setProcessingStatus: (isProcessing: boolean, message?: string) => void;
  setSocketError: (error: string | null) => void;
  triggerToastNotification: (message: string) => void;
  clearSocketStatus: () => void;
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
      savedApiKey: '',
      setLLMConfig: (provider, model, apiKey) => 
        set({ activeProvider: provider, activeModel: model, savedApiKey: apiKey }),
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
  

  setConnectionStatus: (status) => set({ isConnected: status }),
  
  setProcessingStatus: (isProcessing, message = '') =>
    set((state) => ({ isProcessing, statusMessage: message, socketError: isProcessing ? null : state.socketError })),
    
  setSocketError: (error) => set({ socketError: error, isProcessing: false, statusMessage: '' }),
    
  clearSocketStatus: () => set({ isProcessing: false, statusMessage: '', socketError: null }),

  triggerToastNotification: (message) => set({ activeToast: message }),
  clearActiveToast: () => set({ activeToast: null })
}));
