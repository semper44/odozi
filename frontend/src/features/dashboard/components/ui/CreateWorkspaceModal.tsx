// WorkspaceModal.tsx
import React, { useState } from "react";
import { useCreateWorkspaceMutation } from "@/features/odozi/hooks/useRepoMutations";
import { X, Loader2 } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const WorkspaceModal = ({ isOpen, onClose }: ModalProps) => {
  const [workspaceName, setWorkspaceName] = useState("");
  const createWorkspaceMutation = useCreateWorkspaceMutation();

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceName.trim()) return;

    createWorkspaceMutation.mutate(workspaceName, {
      onSuccess: () => {
        setWorkspaceName("");
        onClose(); // Cleanly close the modal overlay window view
        alert("🏢 New organization workspace setup complete!");
      },
      onError: (err: any) => {
        alert(`❌ View constraint rejection: ${err.message}`);
      }
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      {/* Absolute bounding clickable backdrop shield block */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Main Core Modal card structure block container panel */}
      <div className="bg-white rounded-2xl w-full max-w-md p-6 border border-gray-100 shadow-2xl relative z-10 animate-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold text-gray-900">Create New Workspace</h3>
          <button onClick={onClose} className="p-1 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
              Workspace Profile Name
            </label>
            <input
              type="text"
              required
              disabled={createWorkspaceMutation.isPending}
              placeholder="e.g., OdoziEngine Enterprise"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              className="w-full p-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-blue-500 bg-gray-50/50 disabled:opacity-50"
            />
          </div>

          <div className="flex items-center gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 cursor-pointer py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createWorkspaceMutation.isPending || !workspaceName.trim()}
              className="flex items-center gap-2 bg-purple-500 text-white font-semibold text-sm px-5 py-2.5 rounded-xl hover:bg-blue-700 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-blue-100"
            >
              {createWorkspaceMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <span>Create Workspace</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
