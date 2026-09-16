import { useState } from "react";
import { toast } from 'react-toastify';
import { Plus } from "lucide-react";

interface EnvVarModalProps {
  isOpen: boolean;
  onClose: () => void;
  selected: Set<string>; 
  workspace: string
  onSubmit: (keyList: string[], workspace: string) => void;
  isPending: boolean;
}

export function EnvVarModal({ 
  isOpen, 
  onClose, 
  selected,
  workspace,
  onSubmit,
  isPending,
}: EnvVarModalProps) {
  const [currentKey, setCurrentKey] = useState('');
  const [keyList, setKeyList] = useState<string[]>([]);

  if (!isOpen) return null;

  const handleAddKey = () => {
    const trimmed = currentKey.trim().toUpperCase();
    if (!trimmed) return;
    
    if (keyList.includes(trimmed)) {
      toast.warn("This environment variable key has already been added.");
      return;
    }
    if (selected.size < 1 && workspace === "") {
      toast.warn("Please close the modal and select the Repo for this Env vars");
      return;
    }

    setKeyList([...keyList, trimmed]);
    setCurrentKey('');
  };

  const handleRemoveKey = (indexToRemove: number) => {
    setKeyList(keyList.filter((_, idx) => idx !== indexToRemove));
  };

  const handleBulkSubmit = () => {
    if (keyList.length === 0) {
      toast.error("Please add at least one environment variable key.");
      return;
    }

    // Passes the populated string list directly up to createEnvVar()
    onSubmit(keyList, workspace);
  };

   return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg p-6 border border-gray-100 shadow-2xl relative z-10">
        {(workspace === "" && selected.size > 0) &&<p className="text-xs text-gray-500 mt-0.5">
          <span className="text-blue-600 font-bold text-md">{selected.size}</span> repository selected, you can select a workspace as well
        </p>}
        {(workspace != "" && selected.size < 1) &&<p className="text-xs text-gray-500 mt-0.5">
          <span className="text-blue-600 font-bold text-md">{workspace}</span> workspace selected, you can select a repo as well
        </p>}
       {(workspace != "" && selected.size > 0) &&<p className="text-xs text-gray-500 mt-0.5">
          <span className="text-blue-600 font-bold text-md">{selected.size}</span> repository and <span className="text-blue-600 font-bold text-md">{workspace}</span> workspace selected
        </p>}
       {(workspace === "" && selected.size < 1) &&<p className="text-xs text-red-600 font-bold text-md mt-0.5">
          No workspace nor repo selected!
        </p>}
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
            className="p-1 bg-green-500 hover:bg-green-700 rounded-full text-white cursor-pointer font-semibold px-2 transition"
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
            disabled={isPending} // 3. Use React Query's built-in pending state automatically!
            className="rounded cursor-pointer bg-green-500 px-5 py-2 text-white text-sm font-semibold hover:bg-green-700 disabled:bg-purple-800 transition"
          >
            {isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}
