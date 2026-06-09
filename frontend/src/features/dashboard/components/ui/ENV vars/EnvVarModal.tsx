import { useState } from 'react';
import { toast } from 'react-toastify';
import { Plus } from "lucide-react";


interface EnvVarModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EnvVarModal({ isOpen, onClose }: EnvVarModalProps) {
  const [currentKey, setCurrentKey] = useState('');
  const [keyList, setKeyList] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleAddKey = () => {
    const trimmed = currentKey.trim().toUpperCase(); // Enforce uppercase convention
    if (!trimmed) return;
    
    if (keyList.includes(trimmed)) {
      toast.warn("This environment variable key has already been added.");
      return;
    }

    setKeyList([...keyList, trimmed]);
    setCurrentKey('');
  };

  const handleRemoveKey = (indexToRemove: number) => {
    setKeyList(keyList.filter((_, idx) => idx !== indexToRemove));
  };

  const handleBulkSubmit = async () => {
    if (keyList.length === 0) {
      toast.error("Please add at least one environment variable key.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch('/api/repos/env-keys/create/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key_names: keyList,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to save environment variables.');
      }

      toast.success(data.message || "Environment keys saved successfully!");
      setKeyList([]);
      onClose();
    } catch (err: any) {
      toast.error(`❌ ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl w-full max-w-lg p-6 border border-gray-100 shadow-2xl relative z-10 animate-in zoom-in-95 duration-150">
        <h2 className="text-xl font-bold mb-4">Required Environment Variables</h2>
        
        {/* Input Row */}
        <div className="flex items-center space-x-2 mb-4">
          <input
            type="text"
            placeholder="e.g. DATABASE_URL"
            value={currentKey}
            onChange={(e) => setCurrentKey(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddKey()}
            className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-gray-700 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <button 
            type="button"
            onClick={handleAddKey}
            className="p-1 bg-green-500 hover:bg-green-700 rounded-full text-white cursor-pointer font-semibold px-2 hover:text-purple-400 transition"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Keys Area */}
        <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-xl p-2 space-y-2 mb-6 custom-scrollbar">
          {keyList.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No variable keys added yet.</p>
          ) : (
            keyList.map((key, idx) => (
              <div key={idx} className="flex items-center justify-between text-gray-700 px-3 py-1.5 rounded text-sm font-mono border border-gray-300">
                <span>{key}</span>
                <button 
                  onClick={() => handleRemoveKey(idx)} 
                  className="text-gray-500 hover:text-red-400 cursor-pointer font-sans"
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>

        {/* Modal Actions Footer */}
        <div className="flex justify-end space-x-3">
          <button 
            onClick={onClose} 
            className="px-4 py-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition"
          >
            Cancel
          </button>
          <button 
            onClick={handleBulkSubmit}
            disabled={isSubmitting}
            className="rounded cursor-pointer bg-green-500 px-5 py-2 text-white text-sm font-semibold hover:bg-green-700 disabled:bg-purple-800 transition"
          >
            {isSubmitting ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}
