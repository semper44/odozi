import { useSelectionStore } from "@/features/store/selectionStore";

interface Props {
  id: string;
  name: string;
  image: string;
  workspaceName: string;
  isActive:  boolean
}

export const RepoCard = ({
  id,
  name,
  image,
  workspaceName,
  isActive,

}: Props) => {
  const selected = useSelectionStore(
    (state) => state.selected
  );

  const toggleSelect = useSelectionStore(
    (state) => state.toggleSelect
  );

  const isSelected = selected.has(id);

  return (
    <div
      onClick={() => toggleSelect(id)}
      className={`
        border
        p-4
        transition
        flex items-center 
        border-gray-200
        justify-between p-3 rounded-xl cursor-pointer transition-all 
        ${
          isSelected
            ? "bg-blue-100 border-blue-500"
            : "bg-white"
        }
      `}
    >

 
    {/* Left Side: Repo info & Details */}
    <div className="flex flex-col items-start gap-4 min-w-0">
        <img 
            src={image} 
            alt={name} 
            className="w-10 h-10 rounded-full bg-gray-100 flex-shrink-0"
        />
        <div className="min-w-0">
            <p className="font-medium text-gray-900 truncate text-sm sm:text-base">
                {name}
            </p>
            <p className="text-gray-500 text-xs">
                {workspaceName}
            </p>
        </div>
    </div>

    {/* Right Side: Action Target aligned perfectly */}
    <div className="flex-shrink-0 ml-4">
        <div className={`rounded-md cursor-pointer px-4 py-2 text-center h-fit transition-colors min-w-[80px] ${
            isSelected ? "bg-red-500 text-white" : "bg-green-500 text-white hover:bg-green-600"
        }`}>
            <p className="text-sm font-semibold">
                {isSelected ? "Deselect" : "Select"}
            </p>
        </div>
    </div>

    </div>
  );
};