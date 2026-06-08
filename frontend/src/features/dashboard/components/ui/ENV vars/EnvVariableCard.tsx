import { useState, useMemo, useRef, useEffect } from "react";
import { ChevronDown, Search } from "lucide-react";

interface DropdownProps {
  workspaces: string[];
  selectedWorkspace: string;
  onSelectWorkspace: (ws: string) => void;
}

export const EnvVariableCard = () => {
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


  return (
    
  );
};
