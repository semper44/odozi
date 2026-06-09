import React, { useState } from 'react';
import { toast } from 'react-toastify';

// Hardcoded platform and models layout tree configuration
const LLM_PROVIDERS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini', 'o1-preview'],
  anthropic: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus-20240229'],
  google: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash']
};

interface LLMConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LLMConfigModal({ isOpen, onClose }: LLMConfigModalProps) {
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setProvider(e.target.value);
    setModel(''); // Reset structural leaf selections safely on change
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provider || !model || !apiKey.trim()) {
      toast.error("Please complete all configuration fields.");
      return;
    }

    setIsSubmitting(true);
    try {
      // Replace with your actual backend integration destination
      console.log({ provider, model, apiKey });
      toast.success("LLM Configuration stored successfully!");
      onClose();
    } catch (err: any) {
      toast.error(`Error saving setup configuration: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl w-full max-w-lg p-6 border border-gray-100 shadow-2xl relative z-10 animate-in zoom-in-95 duration-150">
        <h2 className="text-xl font-bold mb-4">Configure LLM Credentials</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Dropdown 1: Provider selection */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Select LLM Provider</label>
            <select
              value={provider}
              onChange={handleProviderChange}
              className="w-full rounded border border-gray-700  px-3 py-2 text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">-- Choose Provider --</option>
              <option value="openai">OpenAI (GPT)</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="google">Google (Gemini)</option>
            </select>
          </div>

          {/* Dropdown 2: Dynamic downstream sub-models list mapping */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Select Model Variant</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={!provider}
              className="w-full rounded border border-gray-700  px-3 py-2 text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50"
            >
              <option value="">-- Choose Model --</option>
              {provider && LLM_PROVIDERS[provider].map((modelName) => (
                <option key={modelName} value={modelName}>{modelName}</option>
              ))}
            </select>
          </div>

          {/* Input 3: Platform API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Provider API Key</label>
            <input
              type="password"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full rounded border border-gray-700  px-3 py-2 text-gray-700 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Actions Block */}
          <div className="flex justify-end space-x-3 pt-2">
            <button 
              type="button"
              onClick={onClose} 
              className="px-4 py-2 text-sm cursor-pointer text-gray-400 hover:text-gray-700 transition"
            >
              Cancel
            </button>
            <button 
              type="submit"
              disabled={isSubmitting}
              className="rounded bg-green-500 px-5 py-2 text-sm font-semibold hover:bg-green-700 disabled: cursor-pointer text-white transition"
            >
              Save Configuration
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
