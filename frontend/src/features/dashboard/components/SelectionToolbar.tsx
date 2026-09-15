// SelectionToolbar.tsx

import { useSelectionStore } from "@/features/store/selectionStore";
import { Check, Power, Trash2 } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";

interface Props {
    isOn: boolean;
    switchOn: Dispatch<SetStateAction<boolean>>; 
    filteredRepos: Array<{ id: string | number; [key: string]: any }>; // ✅ ADDED: Accept dynamic filtered array
}
export const SelectionToolbar = ({
    switchOn,
    isOn,
    filteredRepos
}: Props) => {

  const selected = useSelectionStore(
    (state) => state.selected
  );

  const clearSelection = useSelectionStore(
    (state) => state.clearSelection
  );

  const selectAll = useSelectionStore(
    (state) => state.selectAll
  );

//   Derive state for deselecting
//   const allSelected = selected.size === dummyRepos.length;
  
//    # ✅ CRITICAL SHIFT: Determine if all VISIBLE repos are currently selected
  const allVisibleSelected = filteredRepos?.length > 0 && 
    filteredRepos.every((repo) => selected.has(String(repo.id)));

//   Manage the display text state toggle based on your active visible set boundaries
  const displayIsOn = filteredRepos?.length > 0 && allVisibleSelected;


  return (
    <div className="w-full flex gap-4 mb-6 items-center justify-between">
        <button
            onClick={() => {
                if (displayIsOn) {
                    //  If all filtered items are already selected, drop their selections
                    //  You can either clear EVERYTHING or selectively deselect just this filtered array list
                    clearSelection();
                    switchOn(false);
                } else {
                    //  Extract string identifiers mapping ONLY your searched items
                    const idsToSelect = filteredRepos.map((repo) => String(repo.id));
                    selectAll(idsToSelect);
                    switchOn(true);
                }
            }}
            disabled={filteredRepos?.length === 0} //Prevent clicks if search returns zero results
            className={`
                flex items-center cursor-pointer gap-3 px-5 py-2.5 rounded-xl font-medium text-sm
                border-2 tracking-wide shadow-sm transition-all duration-300 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed
                
                ${displayIsOn 
                ? "border-green-500 bg-green-50/60 text-green-700 hover:bg-green-100" 
                : "border-gray-300 bg-gray-50/50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                }
            `}
        >
            <span className={`
                w-2.5 h-2.5 rounded-full transition-transform duration-300
                ${displayIsOn ? "bg-green-500 scale-110 animate-pulse" : "bg-gray-400"}
            `} />

            <span>
                {displayIsOn ? "Clear Filtered" : "Select Filtered"}
            </span>

            {displayIsOn ? (
                <Check className="w-4 h-4 text-green-600" />
            ) : (
                <Power className="w-4 h-4 text-gray-400" />
            )}
        </button>

{/* Right Side: Status Count & Conditional DESELECT ALL Button */}
        {selected.size >= 1 && (
            <div className="flex items-center gap-4 animate-in fade-in slide-in-from-right-4 duration-200">
                {/* Active Selection Tracker Label */}
                <p className="text-sm font-medium text-white bg-purple-500 px-3 py-1.5 rounded-lg">
                    {selected.size} selected
                </p>

                {/* ✅ ADDED: High-Utility Deselect All Action Button */}
                <button
                    onClick={() => {
                        clearSelection();  //Wipes the Zustand Set instantly
                        switchOn(false);    //Resets toolbar toggle state
                    }}
                    className="flex items-center gap-2 cursor-pointer px-4 py-2.5 rounded-xl text-sm font-semibold
                               bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 hover:text-red-700 
                               transition-all duration-200 shadow-sm"
                >
                    <Trash2 className="w-4 h-4" />
                    <span>Deselect All</span>
                </button>
            </div>
        )}    </div>
  );
};