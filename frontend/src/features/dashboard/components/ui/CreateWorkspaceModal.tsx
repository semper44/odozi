// WorkspaceModal.tsx
import React, { useState, useMemo } from "react";
import { X, Search, Loader2, FolderPlus, Check, Square } from "lucide-react";

interface RepositoryItem {
  id: number;
  name: string;
  full_name: string;
}

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  allRepositories: RepositoryItem[]; // ✅ Receives ALL repositories from React-Query cache
  selectedIds: Set<string>;          // ✅ Receives the global selection Set string keys reference
  onToggleSelect: (id: string) => void; // ✅ Receives the global store toggle function
  onSubmit: (payload: { workspaceName: string }) => void;
  isPending: boolean;
}

export const WorkspaceModal = ({
  isOpen,
  onClose,
  allRepositories,
  selectedIds,
  onToggleSelect,
  onSubmit,
  isPending,
}: ModalProps) => {
  const [workspaceName, setWorkspaceName] = useState("");
  const [repoSearchQuery, setRepoSearchQuery] = useState("");

  // Filter the complete GitHub dataset using the modal's internal text search field
  const filteredRepos = useMemo(() => {
    return allRepositories.filter((repo) =>
      repo.full_name.toLowerCase().includes(repoSearchQuery.toLowerCase().trim())
    );
  }, [allRepositories, repoSearchQuery]);

  if (!isOpen) return null;

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceName.trim() || selectedIds.size === 0) return;
    onSubmit({ workspaceName: workspaceName.trim() });
  };

  // Helper utility function to derive the first 2 letters of a repository name for avatar tags
  const getFirstTwoLetters = (fullName: string) => {
    // Extract name after slug slash: "owner/repo-name" -> "repo-name"
    const repoName = fullName.split("/")[1] || fullName;
    return repoName.substring(0, 2).toUpperCase();
  };

  return (
    // Expanded backdrop blurring canvas layer panel overlay layout
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
      <div className="absolute inset-0" onClick={onClose} />

      {/* 🚀 UPGRADED: Expanded max-w-lg sizing bounds providing optimal screen spacing */}
      <div className="bg-white rounded-2xl w-full max-w-lg p-6 border border-gray-100 shadow-2xl relative z-10 animate-in zoom-in-95 duration-150">
        
        {/* Header Section */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-base font-bold text-gray-900">Create a Workspace</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              <span className="text-blue-600 font-bold text-md">{selectedIds.size}</span> repository selected
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-4">
          {/* 1. TOP ELEMENT: Workspace Title Input Text Field */}
          <div>
            <label className="block text-xs font-bold text-gray-500 mb-1.5 uppercase tracking-wider">
              Workspace Profile Name
            </label>
            <div className="relative flex items-center bg-white border border-gray-200 rounded-xl px-3 py-2.5 focus-within:border-blue-500 transition-all">
              <FolderPlus className="w-4 h-4 text-gray-400 mr-2" />
              <input
                type="text"
                required
                disabled={isPending}
                placeholder="e.g., Enterprise Production Cluster"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                className="w-full text-sm outline-none text-gray-700"
              />
            </div>
          </div>

          {/* 2. CORE ELEMENT: Integrated Search & Selection Board Grid */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider">
              Search & Select Repositories
            </label>
            
            {/* Modal Inner Search Bar */}
            <div className="relative flex items-center bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
              <Search className="w-3.5 h-3.5 text-gray-400 mr-2" />
              <input
                type="text"
                placeholder="Type to filter global repository lists..."
                value={repoSearchQuery}
                onChange={(e) => setRepoSearchQuery(e.target.value)}
                className="w-full bg-transparent text-xs outline-none text-gray-700"
              />
            </div>

            {/* 📜 Scrollable List View Frame: Bounded to hold max 3 rows at once using strict CSS dimensions */}
            <div className="max-h-[148px] overflow-y-auto border border-gray-100 rounded-xl p-1 bg-gray-50/40 space-y-1 custom-scrollbar">
              {filteredRepos.map((repo) => {
                const isChecked = selectedIds.has(String(repo.id));

                return (
                  <div
                    key={repo.id}
                    onClick={() => onToggleSelect(String(repo.id))}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer select-none transition-all duration-150 ${
                      isChecked 
                        ? "bg-green-50/50 border border-green-400/60" 
                        : "bg-white border border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    {/* Left item side containing shorthand avatars and label strings */}
                    <div className="flex items-center gap-3 min-w-0">
                      {/* ✅ TWO-LETTER MINI BADGE AVATAR TAG: Highly space optimized! */}
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 transition-colors ${
                        isChecked ? "bg-green-500 text-white" : "bg-gray-100 text-gray-500"
                      }`}>
                        {getFirstTwoLetters(repo.full_name)}
                      </div>
                      
                      <span className="text-xs font-medium text-gray-700 truncate max-w-[280px]">
                        {repo.full_name}
                      </span>
                    </div>

                    {/* Right item side showing action icons */}
                    <div className="flex-shrink-0 ml-4">
                      {isChecked ? (
                        <div className="flex items-center gap-1.5 text-[10px] font-bold text-red-500 bg-red-50 px-2 py-1 rounded-md border border-red-100 hover:bg-red-100 transition-colors">
                          <X className="w-3 h-3" />
                          <span>Cancel</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 text-[10px] font-bold text-green-600 bg-green-50 px-2 py-1 rounded-md border border-green-100 hover:bg-green-500 hover:text-white transition-colors">
                          <Check className="w-3 h-3" />
                          <span>Select</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {filteredRepos.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-6">No matching repositories found on network cache.</p>
              )}
            </div>
          </div>

          {/* Action Submission Buttons block */}
          <div className="flex items-center gap-3 justify-end pt-3 border-t border-gray-100">
            <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors">
              Cancel
            </button>
            
            <button
              type="submit"
              disabled={isPending || !workspaceName.trim() || selectedIds.size === 0}
              className="flex items-center cursor-pointer gap-2 bg-purple-500 text-white font-semibold text-sm px-5 py-2.5 rounded-xl hover:bg-purple-700 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-blue-100"
            >
              {isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <span>Create workspace</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
