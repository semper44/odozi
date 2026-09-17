// SelectionToolbar.tsx

import { items as dummyRepos } from "@/features/data/dummyData";
import { useSelectionStore } from "@/features/store/selectionStore";
import { Check, Power } from "lucide-react";
import type { Dispatch, SetStateAction } from "react"

interface Props {
    isOn: boolean;
    switchOn: Dispatch<SetStateAction<boolean>>; 
}
export const SelectionToolbar = ({
    switchOn,
    isOn
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
  const allSelected = selected.size === dummyRepos.length;
  

  return (
    <div className="w-full flex gap-4 mb-6 items-center justify-between">
        <button
            onClick={() => {
                    if (displayIsOn) {
                        clearSelection();
                        switchOn(false);
                    } else {
                        const idsToSelect = filteredRepos.map(
                            (repo) => String(repo.id)
                        );

                        selectAll(idsToSelect);
                        switchOn(true);
                    }
            }}
            className={`
                flex items-center cursor-pointer gap-3 px-5 py-2.5 rounded-xl font-medium text-sm
                border-2 tracking-wide shadow-sm transition-all duration-300 ease-in-out
                
                ${isOn 
                ? "border-green-500 bg-green-50/60 text-green-700 hover:bg-green-100" 
                : "border-gray-300 bg-gray-50/50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                }
            `}
        >
            {/* Visual State Indicator Dot */}
            <span className={`
                w-2.5 h-2.5 rounded-full transition-transform duration-300
                ${isOn ? "bg-green-500 scale-110 animate-pulse" : "bg-gray-400"}
            `} />

            {/* Button Action Text */}
            <span>
                {isOn ? "Clear All" : "Seclect All"}
            </span>

            {/* State Icon Indicator */}
            {isOn ? (
                <Check className="w-4 h-4 text-green-600" />
            ) : (
                <Power className="w-4 h-4 text-gray-400" />
            )}
        </button>

     {selected.size >= 1 && (<p className="text-md text-green-500">{selected.size} selected</p>)}
    </div>
  );
};