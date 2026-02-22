import { Music, MoreVertical, Play } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { Player } from "@/types/player";
import { formatTime } from "@/lib/utils";
import { proxyThumb } from "@/lib/api";
import { api } from "@/lib/api";

interface SessionTrack {
  title: string;
  author: string;
  uri: string;
  thumbnail: string | null;
  duration: number;
}

interface SessionQueue {
  tracks: SessionTrack[];
  current_index: number;
}

interface QueueSectionProps {
  currentPlayer: Player;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  controlPlayer: (action: string, options?: { query?: string; index?: number; enabled?: boolean; mode?: string }) => void;
  formatTime: (ms: number) => string;
  handleRemoveTrack: (index: number) => void;
  handlePlayNext: (index: number) => void;
  performSearch: (query: string) => Promise<any[]>;
  selectedGuild: string;
}

export default function QueueSection({
  currentPlayer,
  searchQuery,
  setSearchQuery,
  controlPlayer,
  handleRemoveTrack,
  handlePlayNext,
  performSearch,
  selectedGuild,
}: QueueSectionProps) {
  const [openMenuIndex, setOpenMenuIndex] = useState<number | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [isQueueActive, setQueueActive] = useState("Queue");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Session queue state
  const [session, setSession] = useState<SessionQueue>({ tracks: [], current_index: -1 });
  const currentRowRef = useRef<HTMLDivElement | null>(null);

  // Poll session queue every 3 seconds
  useEffect(() => {
    if (!selectedGuild || isQueueActive !== "Queue") return;

    const fetch = async () => {
      try {
        const { data } = await api.get(`/bot/session-queue?guild_id=${selectedGuild}`);
        setSession(data);
      } catch {
        // silent — bot may not be connected
      }
    };

    fetch();
    const id = setInterval(fetch, 3000);
    return () => clearInterval(id);
  }, [selectedGuild, isQueueActive]);

  // Auto-scroll to playing track when it changes
  useEffect(() => {
    currentRowRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [session.current_index]);

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
      setMenuPosition({ x: rect.left - 120, y: rect.top });
    }
  };

  useEffect(() => {
    const handleClickOutside = () => {
      setOpenMenuIndex(null);
      setMenuPosition(null);
    };
    if (openMenuIndex !== null) {
      window.addEventListener("click", handleClickOutside);
    }
    return () => window.removeEventListener("click", handleClickOutside);
  }, [openMenuIndex]);

  const handleTrackClick = (index: number) => {
    controlPlayer("play-index", { index });
  };

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
          Queue ({session.tracks.length})
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

      {/* Content */}
      <div className="flex-1 px-1 overflow-hidden flex flex-col">
        {isQueueActive === "Search" ? (
          <div className="flex flex-col h-full px-1">
            <div className="sticky top-0 z-10 bg-[#0b0d0b] pb-2">
              <input
                type="text"
                placeholder="🔍 Search songs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-stone-300"
              />
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1 max-h-112.5 custom-scrollbar">
              {isSearching ? (
                <div className="text-center text-gray-500 mt-4">Searching...</div>
              ) : searchResults.map((track: any, index: number) => (
                <div
                  key={index}
                  className="relative group flex items-center space-x-3 p-2 hover:bg-neutral-800 rounded-lg transition-colors cursor-pointer"
                  onClick={() => {
                    controlPlayer("play", { query: track.playQuery || track.uri || `${track.title} ${track.author || ""}`.trim() });
                    setQueueActive("Queue");
                  }}
                >
                  <div className="w-14 h-10 relative rounded overflow-hidden flex items-center justify-center bg-neutral-800">
                    <img
                      src={proxyThumb(track.thumbnail)}
                      alt={track.title}
                      className="object-cover w-full h-full"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; (e.currentTarget.nextSibling as HTMLElement).style.display = "flex"; }}
                    />
                    <div style={{ display: "none" }} className="absolute inset-0 flex items-center justify-center">
                      <Music className="h-4 w-4 text-neutral-600" />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{track.title}</p>
                    <p className="text-xs text-gray-400 truncate">{track.author || "Unknown"}</p>
                  </div>
                </div>
              ))}
              {!isSearching && searchResults.length === 0 && (
                <div className="text-center text-gray-500 mt-4">Type and press Enter to search</div>
              )}
            </div>
          </div>
        ) : (
          <>
            {session.tracks.length > 0 ? (
              <div className="space-y-1 overflow-y-auto pr-1 h-full custom-scrollbar pb-40">
                {session.tracks.map((track, index) => {
                  const isCurrent = index === session.current_index;
                  const isPlayed = index < session.current_index;

                  return (
                    <div
                      key={index}
                      ref={isCurrent ? currentRowRef : null}
                      onClick={() => handleTrackClick(index)}
                      className={`relative group flex items-center space-x-3 p-2 rounded-lg transition-all cursor-pointer
                        ${isCurrent
                          ? "bg-neutral-800 border-l-2 border-green-500"
                          : isPlayed
                          ? "opacity-50 hover:opacity-80 hover:bg-neutral-800/60"
                          : "hover:bg-neutral-800"
                        }`}
                    >
                      {/* Thumbnail / play icon overlay */}
                      <div className="w-10 h-10 relative rounded overflow-hidden shrink-0 bg-neutral-800">
                        <img
                          src={proxyThumb(track.thumbnail)}
                          alt={track.title}
                          className="object-cover w-full h-full"
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).style.display = "none";
                            (e.currentTarget.nextSibling as HTMLElement).style.display = "flex";
                          }}
                        />
                        <div style={{ display: "none" }} className="absolute inset-0 flex items-center justify-center">
                          <Music className="h-4 w-4 text-neutral-600" />
                        </div>
                        {/* Play icon on hover */}
                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                          <Play className="h-4 w-4 text-white fill-white" />
                        </div>
                        {/* Equalizer animation for current */}
                        {isCurrent && currentPlayer.playing && !currentPlayer.paused && (
                          <div className="absolute inset-0 bg-black/40 flex items-end justify-center gap-0.5 pb-1 group-hover:hidden">
                            <span className="w-0.5 bg-green-400 animate-[equalizerA_0.8s_ease-in-out_infinite]" style={{ height: "40%" }} />
                            <span className="w-0.5 bg-green-400 animate-[equalizerB_0.6s_ease-in-out_infinite]" style={{ height: "70%" }} />
                            <span className="w-0.5 bg-green-400 animate-[equalizerA_0.9s_ease-in-out_infinite_0.2s]" style={{ height: "55%" }} />
                          </div>
                        )}
                      </div>

                      {/* Track info */}
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate cursor-default ${isCurrent ? "text-green-400" : "text-white"}`} title={track.title}>
                          {track.title}
                          {isCurrent && <span className="ml-2 text-xs text-green-500 font-normal">▶ Playing</span>}
                        </p>
                        <p className="text-xs text-gray-400 truncate">{track.author}</p>
                      </div>

                      {/* Duration */}
                      <span className="text-xs text-gray-500 shrink-0">{formatTime(track.duration)}</span>

                      {/* Context menu */}
                      <button
                        onClick={(e) => { e.stopPropagation(); handleMenuClick(e, index); }}
                        className="p-1 hover:bg-neutral-700 rounded-full transition-colors shrink-0"
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
          style={{ top: `${menuPosition.y}px`, left: `${menuPosition.x}px` }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => { handlePlayNext(openMenuIndex); setOpenMenuIndex(null); }}
            className="w-full px-4 py-2 hover:bg-neutral-800 text-white text-left text-sm flex items-center gap-2"
          >
            Play Next
          </button>
          <button
            onClick={() => { handleRemoveTrack(openMenuIndex); setOpenMenuIndex(null); }}
            className="w-full px-4 py-2 hover:bg-neutral-800 text-red-500 text-left text-sm flex items-center gap-2"
          >
            Remove
          </button>
        </div>
      )}
    </div>
  );
}
