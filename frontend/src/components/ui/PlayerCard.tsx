import { useState, useRef, useEffect } from "react";
import {
  Play,
  Music,
  Pause,
  SkipForward,
  SkipBack,
  Volume2,
  VolumeX,
  Shuffle,
  Repeat,
  Repeat1,
  Heart,
  Download,
  MicVocal,
} from "lucide-react";

import QueueSection from "./QueueSection";
import { Player } from "@/types/player";
import FilterMenu from "./FilterMenu";
import AddToPlaylistDialog from "./AddToPlaylistDialog";
import { useAuthStore } from "@/store/useAuthStore";
import { checkTrackInPlaylists, proxyThumb } from "@/lib/api";

export interface PlayerCardProps {
  currentPlayer: Player;
  controlPlayer: (action: string, options?: { query?: string, index?: number, enabled?: boolean, mode?: string }) => void;
  formatTime: (ms: number) => string;
  isMuted: boolean;
  toggleMute: () => void;
  volume: number;
  setVolume: (volume: number) => void;
  loading: boolean;
  seekToPosition: (percentage: number) => void;
  setIsSeekingTimeline: (seeking: boolean) => void;
  selectedGuild: string;
  isSeekingTimeline: boolean;
  performSearch: (query: string) => Promise<any[]>;
}

export default function PlayerCard({
  currentPlayer,
  controlPlayer,
  formatTime,
  isMuted,
  toggleMute,
  volume,
  setVolume,
  loading,
  seekToPosition,
  setIsSeekingTimeline,
  selectedGuild,
  isSeekingTimeline,
  performSearch,
}: PlayerCardProps) {
  const [searchQuery, setSearchQuery] = useState("");
  // const [isSearching, setIsSearching] = useState(false); // Unused for now
  const [dropdownOpen, setDropdownOpen] = useState<number | null>(null);
  const [showVolumeSlider, setShowVolumeSlider] = useState(false);
  const [localProgress, setLocalProgress] = useState(0);
  const [justSeeked, setJustSeeked] = useState(false);
  
  const [isFilterMenuOpen, setIsFilterMenuOpen] = useState(false);
  const [activeFilter, setActiveFilter] = useState("off"); // This should ideally come from backend settings

  const [seekTarget, setSeekTarget] = useState<number | null>(null);

  const [isAddToPlaylistOpen, setIsAddToPlaylistOpen] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [thumbError, setThumbError] = useState(false);
  const user = useAuthStore((state) => state.user);

  // New state for shuffle mode
  const [shuffleEnabled, setShuffleEnabled] = useState(false);

  // --- Volume sync state ---
  const [localVolume, setLocalVolume] = useState<number | undefined>(undefined);

  const localProgressInterval = useRef<any>(null); // Use any to avoid NodeJS error
  const hideVolumeSliderTimeout = useRef<any>(null); 
  const lastUpdateTime = useRef<number | null>(null);

  // Only update local volume from backend when currentPlayer changes
  useEffect(() => {
    if (currentPlayer.settings) {
      setShuffleEnabled(currentPlayer.settings.shuffleEnabled ?? false);
      if (typeof currentPlayer.settings.volume === "number") {
        setLocalVolume(currentPlayer.settings.volume);
      }
    }
    if (typeof currentPlayer.volume === "number") {
      setLocalVolume(currentPlayer.volume);
    }
  }, [currentPlayer.settings, currentPlayer.volume]);

  // Debounced volume update
  const volumeUpdateTimeout = useRef<any>(null);

  const handleVolumeChange = (newVolume: number) => {
    setLocalVolume(newVolume);
    
    if (volumeUpdateTimeout.current) {
        clearTimeout(volumeUpdateTimeout.current);
    }
    
    volumeUpdateTimeout.current = setTimeout(() => {
        setVolume(newVolume); // Triggers API call via parent
    }, 300);
  };

  const toggleShuffle = async () => {
    // Optimistic update
    setShuffleEnabled(!shuffleEnabled);
    controlPlayer('shuffle', { enabled: !shuffleEnabled });
  };

  const toggleRepeat = async () => {
     // Cycle: off -> all -> one -> off
     const modes = ['off', 'all', 'one'];
     const currentMode = currentPlayer.settings?.repeatMode ?? 'off';
     const nextIndex = (modes.indexOf(currentMode) + 1) % modes.length;
     const nextMode = modes[nextIndex];
     
     controlPlayer('repeat', { mode: nextMode });
  };
  
  const handleDownload = () => {
      if (currentPlayer.current && currentPlayer.current.uri) {
          window.open(currentPlayer.current.uri, "_blank");
      }
  };

  const handleRemoveTrack = async (index: number) => {
      controlPlayer('remove', { index });
      setDropdownOpen(null);
  };

  const handlePlayNext = async (index: number) => {
      controlPlayer('playNext', { index });
      setDropdownOpen(null);
  };

  const handleFilterSelect = (filter: string) => {
      setActiveFilter(filter);
      controlPlayer('filter', { mode: filter });
  };



  const showSlider = () => {
    if (hideVolumeSliderTimeout.current)
      clearTimeout(hideVolumeSliderTimeout.current);
    setShowVolumeSlider(true);
  };

  const hideSlider = () => {
    hideVolumeSliderTimeout.current = setTimeout(() => {
      setShowVolumeSlider(false);
    }, 200);
  };

  useEffect(() => {
    if (justSeeked && seekTarget !== null) {
      if (Math.abs(currentPlayer.position - seekTarget) < 1000) {
        setLocalProgress(currentPlayer.position);
        setJustSeeked(false);
        setSeekTarget(null);
      }
      return;
    }
    if (
      currentPlayer.position !== undefined &&
      currentPlayer.position !== null
    ) {
      setLocalProgress(currentPlayer.position);
    }
  }, [
    currentPlayer.current?.uri,
    selectedGuild,
    currentPlayer.position,
    justSeeked,
    seekTarget,
  ]);

  useEffect(() => {
    if (justSeeked) return;
    if (currentPlayer.current && !currentPlayer.paused && !isSeekingTimeline) {
      if (localProgressInterval.current)
        clearInterval(localProgressInterval.current);
      lastUpdateTime.current = performance.now();
      localProgressInterval.current = setInterval(() => {
        if (lastUpdateTime.current !== null) {
          const now = performance.now();
          const elapsed = now - lastUpdateTime.current;
          setLocalProgress((prev) => prev + elapsed);
          lastUpdateTime.current = now;
        }
      }, 50);

      const syncInterval = setInterval(() => {
        setLocalProgress(currentPlayer.position);
      }, 10000);

      return () => {
        if (localProgressInterval.current)
          clearInterval(localProgressInterval.current);
        clearInterval(syncInterval);
        localProgressInterval.current = null;
        lastUpdateTime.current = null;
      };
    } else {
      if (localProgressInterval.current) {
        clearInterval(localProgressInterval.current);
        localProgressInterval.current = null;
      }
      setLocalProgress(currentPlayer.position);
      lastUpdateTime.current = null;
    }
  }, [currentPlayer, isSeekingTimeline, justSeeked]);

  useEffect(() => {
    const checkLike = async () => {
        if (currentPlayer.current && user) {
             try {
                // Handle different track object structures if necessary
                 const uri = currentPlayer.current.uri || (currentPlayer.current as any).info?.uri;
                 if (uri) {
                    const playlists = await checkTrackInPlaylists(user.id, uri);
                    setIsLiked(playlists.length > 0);
                 }
             } catch (e) {
                 console.error("Error checking like status", e);
             }
        } else {
            setIsLiked(false);
        }
    };

    checkLike();
  }, [currentPlayer.current?.uri, user?.id, isAddToPlaylistOpen]);


  // Media Session API integration
  useEffect(() => {
    if (typeof window === "undefined" || !("mediaSession" in navigator)) return;
    if (!currentPlayer.current) return;

    navigator.mediaSession.metadata = new window.MediaMetadata({
      title: currentPlayer.current.title,
      artist: currentPlayer.current.author,
      artwork: [
        {
          src: proxyThumb(currentPlayer.current.thumbnail) || "/placeholder.svg",
          sizes: "300x300",
          type: "image/png",
        },
      ],
    });

    navigator.mediaSession.setActionHandler("play", () => controlPlayer("play"));
    navigator.mediaSession.setActionHandler("pause", () => controlPlayer("pause"));
    navigator.mediaSession.setActionHandler("previoustrack", () => controlPlayer("previous"));
    navigator.mediaSession.setActionHandler("nexttrack", () => controlPlayer("skip"));

    navigator.mediaSession.playbackState = currentPlayer.paused
      ? "paused"
      : "playing";

    return () => {
      navigator.mediaSession.setActionHandler("play", null);
      navigator.mediaSession.setActionHandler("pause", null);
      navigator.mediaSession.setActionHandler("previoustrack", null);
      navigator.mediaSession.setActionHandler("nexttrack", null);
    };
  }, [currentPlayer, controlPlayer]);

  // Reset thumb error when track changes
  useEffect(() => { setThumbError(false); }, [currentPlayer.current?.uri]);

  if (!currentPlayer.current || !currentPlayer.connected) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Music className="h-24 w-24 mx-auto text-gray-600 mb-4" />
          <h2 className="text-2xl font-semibold text-gray-300 mb-2">
            {currentPlayer.connected === false
              ? "Bot is not in a voice channel"
              : "No music playing"}
          </h2>
          <p className="text-gray-500">
            {currentPlayer.connected === false
              ? "Use /join to invite the bot to your voice channel."
              : "Use Discord commands to start playing music"}
          </p>
        </div>
      </div>
    );
  }

  const repeatMode = currentPlayer.settings?.repeatMode ?? "off";

  return (
    <div className="flex flex-col h-full w-full text-white">
      <div className="flex flex-1 overflow-hidden justify-between">
        <div className="flex items-center w-full justify-center p-4 min-w-[300px]">
          {thumbError || !currentPlayer.current.thumbnail ? (
            <div className="w-[300px] h-[300px] rounded-xl shadow-2xl bg-neutral-800 flex items-center justify-center">
              <Music className="h-24 w-24 text-neutral-600" />
            </div>
          ) : (
            <img
              src={proxyThumb(currentPlayer.current.thumbnail)}
              alt="Album Art"
              className="rounded-xl shadow-2xl object-cover w-[300px] h-[300px]"
              onError={() => setThumbError(true)}
            />
          )}
        </div>

        <div className="items-end pr-4">
          <QueueSection
            currentPlayer={currentPlayer}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            controlPlayer={controlPlayer}
            formatTime={formatTime}
            handleRemoveTrack={handleRemoveTrack}
            handlePlayNext={handlePlayNext}
            performSearch={performSearch}
            selectedGuild={selectedGuild}
          />
        </div>
      </div>

      <div className="border-t border-neutral-800 px-4 py-2">
        <div className="items-center space-x-3 w-full px-2">
          <div>
            <h1 className="text-base font-bold">
              {currentPlayer.current.title}
            </h1>
            <p className="text-sm text-gray-300">
              {currentPlayer.current.author}
            </p>
          </div>

          <input
            type="range"
            min={0}
            max={currentPlayer.current.duration}
            value={localProgress}
            disabled={loading}
            onChange={(e) => {
              const newPositionMs = Number(e.target.value);
              setIsSeekingTimeline(true);
              setLocalProgress(newPositionMs);
              setJustSeeked(true);
              setSeekTarget(newPositionMs);
              seekToPosition((newPositionMs / (currentPlayer.current?.duration || 1)) * 100);
              setTimeout(() => {
                setIsSeekingTimeline(false);
              }, 1000);
              setTimeout(() => {
                setJustSeeked(false);
                setSeekTarget(null);
              }, 3000);
            }}
            className="w-full h-1 bg-gray-700 appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #166534 0%, #166534 ${
                (localProgress / currentPlayer.current.duration!) * 100
              }%, #374151 ${
                (localProgress / currentPlayer.current.duration!) * 100
              }%, #374151 100%)`,
            }}
          />

          <div className="flex items-center justify-between w-full text-xs text-gray-400 mt-1">
            <span>{formatTime(localProgress)}</span>
            <span>{formatTime(currentPlayer.current.duration!)}</span>
          </div>
        </div>

        <div className="w-full flex mx-auto space-y-4">
          <div className="flex items-center w-full space-x-2 justify-between px-4">
            <div className="flex items-center justify-center space-x-2">
              <button 
                onClick={() => setIsAddToPlaylistOpen(true)} 
                className={`transition-colors ${isLiked ? "text-green-500" : "hover:text-green-400"}`}
                title="Add to Playlist"
              >
                  <Heart fill={isLiked ? "currentColor" : "none"} />
              </button>
              <AddToPlaylistDialog 
                isOpen={isAddToPlaylistOpen} 
                onClose={() => setIsAddToPlaylistOpen(false)} 
                track={currentPlayer.current} 
                userId={user?.id} 
              />
              <button onClick={handleDownload} className="hover:text-green-400 transition-colors">
                  <Download />
              </button>
            </div>

            <div className="flex justify-center items-center space-x-4">
              <button
                onClick={toggleShuffle}
                className={`p-2 rounded-full transition-colors ${
                  shuffleEnabled
                    ? "bg-green-600 text-white"
                    : "hover:bg-gray-800 text-gray-400"
                }`}
                title="Shuffle"
              >
                <Shuffle className="h-5 w-5" />
              </button>
              <button
                onClick={() => controlPlayer("previous")}
                className="p-3 hover:bg-gray-800 rounded-full transition-colors"
              >
                <SkipBack className="h-6 w-6" />
              </button>
              <button
                onClick={() =>
                  controlPlayer(currentPlayer.paused ? "play" : "pause")
                }
                disabled={loading}
                className="p-4 bg-green-600 hover:bg-green-700 rounded-full transition-colors disabled:opacity-50"
              >
                {currentPlayer.paused ? (
                  <Play className="h-8 w-8 ml-1" />
                ) : (
                  <Pause className="h-8 w-8" />
                )}
              </button>
              <button
                onClick={() => controlPlayer("skip")}
                disabled={loading}
                className="p-3 hover:bg-gray-800 rounded-full transition-colors"
              >
                <SkipForward className="h-6 w-6" />
              </button>
              <button
                onClick={toggleRepeat}
                className={`p-2 rounded-full transition-colors ${
                  repeatMode !== "off"
                    ? "bg-green-600 text-white"
                    : "hover:bg-gray-800 text-gray-400"
                }`}
                title={`Repeat: ${repeatMode}`}
              >
                {repeatMode === "all" ? (
                  <Repeat className="h-6 w-6" />
                ) : repeatMode === "one" ? (
                  <Repeat1 className="h-6 w-6" />
                ) : (
                  <Repeat className="h-6 w-6" />
                )}
              </button>
            </div>

            <div className="flex items-center space-x-2 relative">
              <button
                onClick={() => setIsFilterMenuOpen(!isFilterMenuOpen)}
                className={`p-2 rounded-full transition-colors ${
                  activeFilter !== "off" 
                    ? "text-green-400 bg-green-400/10" 
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
                title="Audio Filters"
              >
                <MicVocal className="h-5 w-5" />
              </button>
              
              <FilterMenu 
                isOpen={isFilterMenuOpen} 
                onClose={() => setIsFilterMenuOpen(false)}
                onSelectFilter={handleFilterSelect}
                activeFilter={activeFilter}
              />

              <div
                className="relative flex items-center"
                onMouseEnter={showSlider}
                onMouseLeave={hideSlider}
              >
                <button
                  onClick={toggleMute}
                  className="p-2 hover:bg-gray-800 rounded-full text-gray-400 hover:text-white transition-colors"
                >
                  {isMuted ? (
                    <VolumeX className="h-5 w-5" />
                  ) : (
                    <Volume2 className="h-5 w-5" />
                  )}
                </button>

                {showVolumeSlider && (
                  <div className="absolute right-0 w-8 bottom-full mb-2 bg-neutral-900 border border-neutral-800 p-3 rounded-xl shadow-2xl flex flex-col items-center justify-center space-y-2 z-10">
                    <div className="h-32 w-full flex items-center justify-center py-2">
                         <input
                            type="range"
                            min={0}
                            max={100}
                            value={isMuted ? 0 : localVolume ?? 100}
                            onChange={(e) => {
                                const newVol = Number(e.target.value);
                                handleVolumeChange(newVol);
                            }}
                            className="w-24 h-1 bg-neutral-700 rounded-lg appearance-none cursor-pointer hover:bg-neutral-600 transition-colors"
                            style={{
                                transform: "rotate(-90deg)",
                                transformOrigin: "center",
                                background: `linear-gradient(to right, #22c55e 0%, #22c55e ${isMuted ? 0 : localVolume ?? 100}%, #404040 ${isMuted ? 0 : localVolume ?? 100}%, #404040 100%)`
                            }}
                        />
                    </div>
                   
                    <span className="text-xs font-mono font-medium text-green-400">
                      {isMuted ? 0 : volume}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {dropdownOpen !== null && (
        <div
          className="fixed inset-0 z-5"
          onClick={() => setDropdownOpen(null)}
        />
      )}
    </div>
  );
}
