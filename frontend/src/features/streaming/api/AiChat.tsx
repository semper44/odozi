import React, { useState } from 'react';
import { toast } from 'react-toastify';

export default function AgenticChatConsole() {
  const [prompt, setPrompt] = useState('');
  const [isPending, setIsPending] = useState(false);
  
  // 🌟 LLM & MODEL CONF SELECTION STATES 
  // Bind these variables straight to your existing modal selection values!
  const [selectedProvider, setSelectedProvider] = useState('gemini'); // e.g., 'gemini', 'openai', 'anthropic'
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash'); 
  const [chatSessionId, setChatSessionId] = useState(1); // Set to active session identifier row integer

  const handleSendPrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const cleanedInput = prompt.trim();
    if (!cleanedInput) return;

    setIsPending(true);
    const toastId = toast.info("Agent computing execution matrix...", { autoClose: false });

    // 1. Pack your universal backend payload block cleanly
    const payload = {
      message: cleanedInput,
      session_id: chatSessionId,
      // Pass these along to future-proof your user subscription tier parameters!
      provider: selectedProvider,
      model_name: selectedModel
    };

    try {
      const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL ;
      
      // 2. Fire the unified payload down to your AITestSummaryView view path
      const response = await fetch(`${backendUrl}/dashboard/api/ai/test-summary/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // "Authorization": `Bearer ${yourAuthToken}` // Uncomment once JWT is re-activated
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      toast.dismiss(toastId);

      if (!response.ok) {
        throw new Error(result.error || `Gateway returned status: ${response.status}`);
      }

      // 3. Clear text fields cleanly upon successful delivery execution
      setPrompt('');
      
      toast.success("🎯 Structure generated perfectly!", { theme: "dark" });
      console.log("Structured AI Output Result Object:", result.data);
      console.log("Token Cost Metadata Readout:", result.usage);

    } catch (err: any) {
      toast.dismiss(toastId);
      toast.error(`❌ Pipeline Sync Error: ${err.message}`);
      console.error("AI View request failure context:", err);
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto p-4 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl">
      
      {/* Visual Diagnostic Indicators (Shows active model selection values tracking) */}
      <div className="flex items-center gap-2 mb-3 px-1 text-[11px] font-mono text-slate-400">
        <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <span>Agent Model Context:</span>
        <span className="bg-slate-800 text-indigo-400 px-1.5 py-0.5 rounded border border-slate-700 font-bold uppercase">
          {selectedProvider}
        </span>
        <span className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700">
          {selectedModel}
        </span>
      </div>

      {/* Main Console Input Area Box */}
      <form onSubmit={handleSendPrompt} className="relative flex items-center">
        <input
          type="text"
          value={prompt}
          // 🌟 Triggers state transformation smoothly on keypress
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isPending}
          placeholder="Ask Odozi to compile workspaces, inject keys, or run AST rules..."
          className="w-full pl-4 pr-12 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-60"
        />
        
        {/* Compact Action Submit Arrow */}
        <button
          type="submit"
          disabled={isPending || !prompt.trim()}
          className={`absolute right-2 p-1.5 rounded-lg text-slate-400 transition-all duration-150 cursor-pointer ${
            !prompt.trim() || isPending
              ? 'opacity-30 cursor-not-allowed'
              : 'text-indigo-400 hover:text-indigo-300 bg-slate-800 hover:bg-slate-700 active:scale-95'
          }`}
        >
          {isPending ? (
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          )}
        </button>
      </form>
    </div>
  );
}
