// WorkspaceDropdown.tsx
import { useState, useMemo, useRef, useEffect } from "react";
import { ChevronDown, Search } from "lucide-react";

interface DropdownProps {
  workspaces: string[];
  selectedWorkspace: string;
  onSelectWorkspace: (ws: string) => void;
}

export const WorkspaceDropdown = ({ workspaces, selectedWorkspace, onSelectWorkspace }: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown if user clicks anywhere outside of it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter workspaces list inside dropdown based on search query
  const filteredWorkspaces = useMemo(() => {
    return workspaces.filter((ws) => ws.toLowerCase().includes(searchQuery.toLowerCase().trim()));
  }, [workspaces, searchQuery]);

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* Main Flex Button Trigger Layout Container */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm select-none"
      >
        <span className="text-sm font-semibold text-gray-700">
          {selectedWorkspace || "All Workspaces"}
        </span>
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </div>

      {/* Dropdown Menu Overlay Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white border border-gray-200 rounded-xl shadow-xl z-50 p-2 animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Inner Search Field */}
          <div className="relative flex items-center mb-2 bg-gray-50 border border-gray-200 rounded-lg px-2 py-1.5">
            <Search className="w-3.5 h-3.5 text-gray-400 mr-2 flex-shrink-0" />
            <input
              type="text"
              placeholder="Search workspaces..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent text-xs outline-none text-gray-700"
            />
          </div>

          {/* Scrollable list bounded to display roughly 3 items maximum at once */}
          <div className="max-h-[132px] overflow-y-auto space-y-0.5 custom-scrollbar">
            <div
              onClick={() => { onSelectWorkspace(""); setIsOpen(false); setSearchQuery(""); }}
              className={`px-3 py-2 text-xs font-medium rounded-lg cursor-pointer transition-colors ${
                !selectedWorkspace ? "bg-blue-50 text-blue-600" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              All Workspaces
            </div>
            
            {filteredWorkspaces.map((ws) => (
              <div
                key={ws}
                onClick={() => { onSelectWorkspace(ws); setIsOpen(false); setSearchQuery(""); }}
                className={`px-3 py-2 text-xs font-medium rounded-lg cursor-pointer transition-colors truncate ${
                  selectedWorkspace === ws ? "bg-blue-50 text-blue-600" : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                {ws}
              </div>
            ))}

            {filteredWorkspaces.length === 0 && (
              <p className="text-[11px] text-gray-400 text-center py-2">No matching workspaces.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
