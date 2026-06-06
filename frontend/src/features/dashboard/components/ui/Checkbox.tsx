import React from "react";
import { Check } from "lucide-react";

interface CheckboxProps {
  checked: boolean;
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export const Checkbox = ({
  checked,
  onChange,
  label,
  disabled = false,
}: CheckboxProps) => {
  const handleToggle = () => {
    if (!disabled && onChange) {
      onChange(!checked);
    }
  };

  return (
    <div 
      onClick={handleToggle}
      className={`flex items-center gap-3 select-none ${
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
      }`}
    >
       <p>All Workspaces</p>
      {/* Outer Wrapper Box Container */}
      <div
        className={`
          w-5 h-5 rounded-md border-2 flex items-center justify-center 
          transition-all duration-200 ease-in-out shadow-sm
          
          ${checked 
            ? "border-green-500 bg-green-500 scale-105" 
            : "border-gray-300 bg-white hover:border-gray-400 focus:border-blue-500"
          }
        `}
      >
       
        {/* Animated Inner Checkmark Icon Anchor */}
        <Check
          className={`
            w-3.5 h-3.5 text-white stroke-[3.5px] transition-all duration-200
            ${checked ? "scale-100 opacity-100" : "scale-50 opacity-0"}
          `}
        />
      </div>

      {/* Optional Side Label Text Rendering */}
      {label && (
        <span className={`text-sm font-medium ${checked ? "text-green-700" : "text-gray-600"}`}>
          {label}
        </span>
      )}
    </div>
  );
};
