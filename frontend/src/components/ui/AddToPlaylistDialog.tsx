import { useState, useEffect, useRef } from "react";
import { 
  getUserPlaylists, 
  createPlaylist, 
  deletePlaylist,
  addTrackToPlaylist, 
  removeTrackFromPlaylist,
  checkTrackInPlaylists 
} from "@/lib/api";

import { Plus, X, Check, Music, Trash2 } from "lucide-react";

interface AddToPlaylistDialogProps {
  isOpen: boolean;
  onClose: () => void;
  track: any; // The current track object
  userId?: string | number;
}

interface Playlist {
  id: number;
  name: string;
  is_liked_songs: boolean;
  track_count: number;
}

interface ContainmentInfo {
  playlist_id: number;
  track_db_id: number;
}

export default function AddToPlaylistDialog({ isOpen, onClose, track, userId }: AddToPlaylistDialogProps) {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [containedIn, setContainedIn] = useState<ContainmentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [creating, setCreating] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const lastFetchedUri = useRef<string | null>(null);

  useEffect(() => {
    // Stable identifier for track (uri)
    const trackUri = track?.uri || track?.info?.uri;

    // Guard: Only fetch if URI actually changed
    if (isOpen && userId && trackUri && trackUri !== lastFetchedUri.current) {
      lastFetchedUri.current = trackUri;
      fetchData();
    }
  }, [isOpen, userId, track?.uri, track?.info?.uri]);

  // Click outside to close
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

  const fetchData = async () => {
    if (!userId || !track) return;
    setLoading(true);
    try {
      const [userPlaylists, containment] = await Promise.all([
        getUserPlaylists(userId),
        checkTrackInPlaylists(userId, track.uri || track.info?.uri),
      ]);
      setPlaylists(userPlaylists);
      setContainedIn(containment);
    } catch (error) {
      console.error("Failed to fetch playlist data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePlaylist = async () => {
    if (!newPlaylistName.trim() || !userId) return;
    setCreating(true);
    try {
      await createPlaylist(newPlaylistName, userId);
      setNewPlaylistName("");
      // Refresh list
      const userPlaylists = await getUserPlaylists(userId);
      setPlaylists(userPlaylists);
    } catch (error) {
      console.error("Failed to create playlist", error);
    } finally {
      setCreating(false);
    }
  };

  const handleDeletePlaylist = async (playlistId: number) => {
    if (!userId || !confirm("Are you sure you want to delete this playlist?")) return;
    try {
        await deletePlaylist(playlistId, userId);
        setPlaylists(prev => prev.filter(p => p.id !== playlistId));
    } catch (error) {
        console.error("Failed to delete playlist", error);
    }
  };

  const togglePlaylist = async (playlist: Playlist) => {
    // Find if valid
    const containment = containedIn.find(c => c.playlist_id === playlist.id);
    
    // Optimization: Optimistic update could be complex due to track_db_id requirement for removal.
    // So we'll just wait for API.
    
    try {
      if (containment) {
        // Remove
        await removeTrackFromPlaylist(playlist.id, containment.track_db_id);
        setContainedIn(prev => prev.filter(c => c.playlist_id !== playlist.id));
      } else {
        // Add
        // Construct a stable track object if needed, or just pass track. 
        // Track from Wavelink might be complex, but backend handles it.
        const res = await addTrackToPlaylist(playlist.id, track);
        if (res.success) {
            setContainedIn(prev => [...prev, { playlist_id: playlist.id, track_db_id: res.track_id }]);
        }
      }
    } catch (error) {
       console.error("Failed to update playlist", error);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="absolute bottom-16 left-0 md:left-auto md:relative z-50">
       {/* Positioning might need adjustment depending on parent. 
           If parent is relative, this works. Using fixed overlay for mobile might be safer.
           For now, mimicking FilterMenu style but maybe centered or near the button?
           Let's use a fixed overlay for better UX on lists.
       */}
       <div className="fixed inset-0 bg-black/50 z-40" />
       
       <div 
         ref={menuRef}
         className="fixed bottom-1/4 left-1/2 transform -translate-x-1/2  w-80 bg-neutral-900 border border-neutral-800 rounded-xl shadow-2xl z-50 animate-in fade-in zoom-in-95"
       >
         <div className="flex items-center justify-between p-4 border-b border-neutral-800">
           <h3 className="text-lg font-semibold text-white">Save to Playlist</h3>
           <button onClick={onClose} className="text-neutral-400 hover:text-white">
             <X className="h-5 w-5" />
           </button>
         </div>

         <div className="p-2 max-h-60 overflow-y-auto space-y-1">
             {loading ? (
                 <div className="text-center text-neutral-500 py-4">Loading...</div>
             ) : (
                  playlists.map(playlist => {
                      const isChecked = containedIn.some(c => c.playlist_id === playlist.id);
                      return (
                          <div key={playlist.id} className="flex items-center group/item hover:bg-neutral-800 rounded-lg p-1 transition-colors">
                              <button
                                onClick={() => togglePlaylist(playlist)}
                                className="flex-1 flex items-center p-2 text-left"
                              >
                                  <div className={`w-5 h-5 border-2 rounded mr-3 flex items-center justify-center transition-colors ${
                                      isChecked ? "bg-green-600 border-green-600" : "border-neutral-600 group-hover/item:border-neutral-500"
                                  }`}>
                                      {isChecked && <Check className="w-3 h-3 text-white" />}
                                  </div>
                                  <div className="flex-1">
                                      <div className="text-white font-medium">{playlist.name}</div>
                                      <div className="text-xs text-neutral-500">{playlist.track_count} tracks</div>
                                  </div>
                                  {playlist.is_liked_songs && <Music className="w-4 h-4 text-purple-400 ml-2" />}
                              </button>

                              {!playlist.is_liked_songs && (
                                  <button
                                      onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeletePlaylist(playlist.id);
                                      }}
                                      className="p-2 text-neutral-500 hover:text-red-500 opacity-0 group-hover/item:opacity-100 transition-all"
                                      title="Delete Playlist"
                                  >
                                      <Trash2 className="w-4 h-4" />
                                  </button>
                              )}
                          </div>
                      );
                  })
              )}
         </div>

         <div className="p-4 border-t border-neutral-800">
            <div className="flex items-center space-x-2">
                <input 
                    type="text" 
                    placeholder="New Playlist Name" 
                    value={newPlaylistName}
                    onChange={(e) => setNewPlaylistName(e.target.value)}
                    className="flex-1 bg-neutral-800 border-none rounded-lg px-3 py-2 text-sm text-white placeholder-neutral-500 focus:ring-1 focus:ring-green-500 outline-none"
                    onKeyDown={(e) => e.key === 'Enter' && handleCreatePlaylist()}
                />
                <button 
                    onClick={handleCreatePlaylist}
                    disabled={newPlaylistName.trim().length === 0 || creating}
                    className="p-2 bg-green-600 hover:bg-green-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Plus className="w-5 h-5" />
                </button>
            </div>
         </div>
       </div>
    </div>
  );
}
