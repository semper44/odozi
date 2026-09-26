import { useSelectionStore } from "@/features/store/selectionStore";
import { Check, Power, Trash2 } from "lucide-react";

interface Props {
    filteredRepos: Array<{ id: string | number; [key: string]: any }>;
}

export const SelectionToolbar = ({filteredRepos,}: Props) => {
    const selected = useSelectionStore((state) => state.selected);

    const clearSelection = useSelectionStore((state) => state.clearSelection);

    const selectAll = useSelectionStore((state) => state.selectAll);

    // Determine whether every currently visible repository is selected.
    const allVisibleSelected =
        filteredRepos.length > 0 &&
        filteredRepos.every((repo) =>
            selected.has(String(repo.id))
        );

    const displayIsOn = filteredRepos.length > 0 && allVisibleSelected;

    return (
        <div className="w-full flex gap-4 mb-6 items-center justify-between">
            <button
                onClick={() => {
                    if (displayIsOn) {
                        clearSelection();
                    } else {
                        const idsToSelect = filteredRepos.map(
                            (repo) => String(repo.id)
                        );

                        selectAll(idsToSelect);
                    }
                }}
                disabled={filteredRepos.length === 0}
                className={`
                    flex items-center cursor-pointer gap-3 px-5 py-2.5 rounded-xl font-medium text-sm
                    border-2 tracking-wide shadow-sm transition-all duration-300 ease-in-out
                    disabled:opacity-50 disabled:cursor-not-allowed

                    ${
                        displayIsOn
                            ? "border-green-500 bg-green-50/60 text-green-700 hover:bg-green-100"
                            : "border-gray-300 bg-gray-50/50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                    }
                `}
            >
                <span
                    className={`
                        w-2.5 h-2.5 rounded-full transition-transform duration-300
                        ${
                            displayIsOn
                                ? "bg-green-500 scale-110 animate-pulse"
                                : "bg-gray-400"
                        }
                    `}
                />

                <span>
                    {displayIsOn ? "Clear Filtered" : "Select Filtered"}
                </span>

                {displayIsOn ? (
                    <Check className="w-4 h-4 text-green-600" />
                ) : (
                    <Power className="w-4 h-4 text-gray-400" />
                )}
            </button>

            {selected.size >= 1 && (
                <div className="flex items-center gap-4 animate-in fade-in slide-in-from-right-4 duration-200">
                    <p className="text-sm font-medium text-white bg-purple-500 px-3 py-1.5 rounded-lg">
                        {selected.size} selected
                    </p>

                    <button
                        onClick={() => {
                            clearSelection();
                        }}
                        className="
                            flex items-center gap-2 cursor-pointer px-4 py-2.5 rounded-xl
                            text-sm font-semibold bg-red-50 text-red-600
                            border border-red-200 hover:bg-red-100 hover:text-red-700
                            transition-all duration-200 shadow-sm
                        "
                    >
                        <Trash2 className="w-4 h-4" />
                        <span>Deselect All</span>
                    </button>
                </div>
            )}
        </div>
    );
};