import { Music, MoreVertical } from "lucide-react";
import { useState, useEffect } from "react";
import { Player } from "@/types/player";
import { formatTime } from "@/lib/utils";

interface QueueSectionProps {
  currentPlayer: Player;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  controlPlayer: (action: string, options?: { query?: string, index?: number, enabled?: boolean, mode?: string }) => void;
  formatTime: (ms: number) => string;
  handleRemoveTrack: (index: number) => void;
  handlePlayNext: (index: number) => void;
  performSearch: (query: string) => Promise<any[]>;
}

export default function QueueSection({
  currentPlayer,
  searchQuery,
  setSearchQuery,
  controlPlayer,
  handleRemoveTrack,
  handlePlayNext,
  performSearch,
}: QueueSectionProps) {
  const [openMenuIndex, setOpenMenuIndex] = useState<number | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  
  const [isQueueActive, setQueueActive] = useState("Queue");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    if (isQueueActive === "Queue") {
      setSearchResults([]);
      setSearchQuery("");
    }
  }, [isQueueActive]);

  const handleSearch = async () => {
      if (!searchQuery.trim()) return;
      setIsSearching(true);
      const results = await performSearch(searchQuery);
      setSearchResults(results);
      setIsSearching(false);
  };

  const handleMenuClick = (e: React.MouseEvent<HTMLButtonElement>, index: number) => {
    e.stopPropagation();
    if (openMenuIndex === index) {
      setOpenMenuIndex(null);
      setMenuPosition(null);
    } else {
       const rect = e.currentTarget.getBoundingClientRect();
       setOpenMenuIndex(index);
       // Position the menu to the left of the button, slightly elevated
       setMenuPosition({ 
           x: rect.left - 120, // Shift left by menu width (approx)
           y: rect.top 
       });
    }
  };

  // Close menu on global click
  useEffect(() => {
      const handleClickOutside = () => {
          setOpenMenuIndex(null);
          setMenuPosition(null);
      };
      if (openMenuIndex !== null) {
          window.addEventListener('click', handleClickOutside);
      }
      return () => window.removeEventListener('click', handleClickOutside);
  }, [openMenuIndex]);


  return (
    <div className="p-4 w-96 flex flex-col h-full overflow-hidden relative">
      {/* Tabs */}
      <div className="flex items-center w-full mb-4">
        <button
          className={`w-1/2 text-base pb-4 text-center font-light uppercase border-b-2 ${
            isQueueActive === "Queue"
              ? "border-neutral-300 text-neutral-200"
              : "border-neutral-700 text-neutral-500"
          }`}
          onClick={() => setQueueActive("Queue")}
        >
          Queue ({currentPlayer?.queue?.length || 0})
        </button>
        <button
          className={`w-1/2 text-base pb-4 text-center font-light uppercase border-b-2 ${
            isQueueActive === "Search"
              ? "border-neutral-300 text-neutral-200"
              : "border-neutral-700 text-neutral-500"
          }`}
          onClick={() => setQueueActive("Search")}
        >
          Search
        </button>
      </div>

      {/* Content wrapper with scroll */}
      <div className="flex-1 px-1 overflow-hidden flex flex-col">
        {isQueueActive === "Search" ? (
          <div className="flex flex-col h-full px-1">
            {/* Sticky Search Bar */}
            <div className="sticky top-0 z-10 bg-[#0b0d0b] pb-2">
              <input
                type="text"
                placeholder="🔍 Search songs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        handleSearch();
                    }
                }}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-stone-300"
              />
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1 max-h-[450px] custom-scrollbar">
              {isSearching ? (
                 <div className="text-center text-gray-500 mt-4">Searching...</div>
              ) : searchResults.map((track: any, index: number) => (
                <div
                  key={index}
                  className="relative group flex items-center space-x-3 p-2 hover:bg-neutral-800 rounded-lg transition-colors cursor-pointer"
                  onClick={() => {
                        controlPlayer("play", { query: track.uri });
                        // Optional: Clear search or give feedback
                        setQueueActive("Queue");
                  }}
                >
                  <div className="w-14 h-10 relative rounded overflow-hidden flex items-center justify-center">
                    <img
                      src={track.thumbnail || "/placeholder.svg"}
                      alt={track.title}
                      className="object-cover w-full h-full"
                    />
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {track.title}
                    </p>
                    <p className="text-xs text-gray-400 truncate">
                      {track.author || "Unknown"}
                    </p>
                  </div>
                </div>
              ))}
              {!isSearching && searchResults.length === 0 && (
                  <div className="text-center text-gray-500 mt-4">
                      Type and press Enter to search
                  </div>
              )}
            </div>
          </div>
        ) : (
          <>
            {currentPlayer?.queue && currentPlayer.queue.length > 0 ? (
              <div className="space-y-2 overflow-y-auto pr-1 h-full custom-scrollbar pb-40">
                {currentPlayer.queue.map((track: any, index: number) => {
                  const thumbnail =
                    track.thumbnail && track.thumbnail.startsWith("http")
                      ? track.thumbnail
                      : "/placeholder.svg";

                  return (
                    <div
                      key={index}
                      className="relative group flex items-center space-x-3 p-2 hover:bg-neutral-800 rounded-lg transition-colors"
                    >
                      <div className="w-10 h-10 relative rounded overflow-hidden flex-shrink-0">
                        <img
                          src={thumbnail}
                          alt={track.title}
                          className="object-cover w-full h-full"
                        />
                      </div>

                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate cursor-default" title={track.title}>
                          {track.title}
                        </p>
                        <p className="text-xs text-gray-400 truncate">
                          {track.author}
                        </p>
                      </div>

                      <span className="text-xs text-gray-500 flex-shrink-0">
                        {formatTime(track.duration)}
                      </span>

                      {/* 3-dot menu trigger */}
                      <button
                        onClick={(e) => handleMenuClick(e, index)}
                        className="p-1 hover:bg-neutral-700 rounded-full transition-colors flex-shrink-0"
                      >
                        <MoreVertical className="h-4 w-4 text-gray-400" />
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8">
                <Music className="h-12 w-12 mx-auto text-gray-600 mb-2" />
                <p className="text-gray-500 text-sm">Queue is empty</p>
              </div>
            )}
          </>
        )}
      </div>

       {/* Fixed Dropdown Menu */}
       {openMenuIndex !== null && menuPosition && (
            <div 
                className="fixed z-50 bg-neutral-900 border border-neutral-700 rounded-md shadow-2xl py-1 w-32"
                style={{
                    top: `${menuPosition.y}px`,
                    left: `${menuPosition.x}px`
                }}
                onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside
            >
            <button
                onClick={() => {
                handlePlayNext(openMenuIndex);
                setOpenMenuIndex(null);
                }}
                className="w-full px-4 py-2 hover:bg-neutral-800 text-white text-left text-sm flex items-center gap-2"
            >
                Play Next
            </button>
            <button
                onClick={() => {
                handleRemoveTrack(openMenuIndex);
                setOpenMenuIndex(null);
                }}
                className="w-full px-4 py-2 hover:bg-neutral-800 text-red-500 text-left text-sm flex items-center gap-2"
            >
                Remove
            </button>
            </div>
        )}
    </div>
  );
}

