import { useRef, useEffect } from "react";
import { Sparkles, X } from "lucide-react";

interface FilterMenuProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectFilter: (filter: string) => void;
  activeFilter?: string;
}

const FILTERS = [
  { id: "off", name: "Normal" },
  { id: "nightcore", name: "Nightcore" },
  { id: "vaporwave", name: "Vaporwave" },
  { id: "karaoke", name: "Karaoke" },
  { id: "8d", name: "8D Audio" },
  { id: "tremolo", name: "Tremolo" },
  { id: "vibrato", name: "Vibrato" },
];

export default function FilterMenu({ isOpen, onClose, onSelectFilter, activeFilter = "off" }: FilterMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div 
      ref={menuRef}
      className="absolute bottom-14 right-0 w-48 bg-neutral-900 border border-neutral-800 rounded-lg shadow-xl overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2"
    >
      <div className="flex items-center justify-between p-3 border-b border-neutral-800 bg-neutral-900/50">
        <div className="flex items-center space-x-2 text-green-400">
          <Sparkles className="h-4 w-4" />
          <span className="text-sm font-semibold">Audio Filters</span>
        </div>
        <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300">
          <X className="h-4 w-4" />
        </button>
      </div>
      
      <div className="p-1 max-h-60 overflow-y-auto">
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            onClick={() => {
              onSelectFilter(filter.id);
              onClose();
            }}
            className={`w-full text-left px-3 py-2 text-sm rounded-md transition-colors flex items-center justify-between ${
              activeFilter === filter.id
                ? "bg-green-600/20 text-green-400"
                : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
            }`}
          >
            <span>{filter.name}</span>
            {activeFilter === filter.id && (
              <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
