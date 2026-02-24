import { useState, useEffect, useRef, useCallback } from "react";
import {
  Plus,
  Trash2,
  Music2,
  ListMusic,
  Play,
  X,
  Search,
  Loader2,
  Clock,
  MoreVertical,
  AlertTriangle,
  CheckCircle,
  Upload,
} from "lucide-react";
import {
  getUserPlaylists,
  createPlaylist,
  deletePlaylist,
  removeTrackFromPlaylist,
  getBotGuilds,
} from "@/lib/api";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

// ---------------------------------------------------------------------------
// Guild Picker Modal
// ---------------------------------------------------------------------------
interface Guild { id: string; name: string; icon: string | null }

function GuildPickerModal({
  onClose,
  onPick,
}: {
  onClose: () => void;
  onPick: (guildId: string) => void;
}) {
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBotGuilds()
      .then((data) => setGuilds(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-bold text-white">Choose a Server</h2>
            <p className="text-xs text-gray-400 mt-0.5">Pick which server to start playing in</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 size={24} className="animate-spin mr-2" /> Loading servers...
          </div>
        ) : guilds.length === 0 ? (
          <p className="text-center text-gray-500 py-8 text-sm">No servers found where the bot is present.</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
            {guilds.map((g) => (
              <button
                key={g.id}
                onClick={() => { onPick(g.id); onClose(); }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-neutral-800 transition text-left"
              >
                {g.icon ? (
                  <img
                    src={`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=32`}
                    className="w-8 h-8 rounded-full"
                    alt={g.name}
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center text-xs font-bold text-gray-300">
                    {g.name.charAt(0)}
                  </div>
                )}
                <span className="text-sm font-medium text-white truncate">{g.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
type ToastType = "warning" | "success" | "error";
interface ToastMsg { id: number; type: ToastType; message: string }

function Toast({ toasts, remove }: { toasts: ToastMsg[]; remove: (id: number) => void }) {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 items-center pointer-events-none">
      {toasts.map((t) => {
        const colors =
          t.type === "warning"
            ? "bg-amber-900/90 border-amber-700 text-amber-200"
            : t.type === "error"
            ? "bg-red-900/90 border-red-700 text-red-200"
            : "bg-green-900/90 border-green-700 text-green-200";
        return (
          <div
            key={t.id}
            className={`flex items-center gap-3 px-5 py-3 rounded-xl border shadow-2xl backdrop-blur-sm pointer-events-auto ${colors} animate-in fade-in slide-in-from-bottom-4`}
          >
            {t.type === "warning" || t.type === "error" ? (
              <AlertTriangle size={18} />
            ) : (
              <CheckCircle size={18} />
            )}
            <span className="text-sm font-medium">{t.message}</span>
            <button onClick={() => remove(t.id)} className="ml-2 opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

interface Track {
  id: number;
  track_data: {
    info?: {
      title: string;
      author: string;
      uri: string;
      length: number;
    };
    title?: string;
    author?: string;
    uri?: string;
    length?: number;
  };
  added_at: string;
}

interface Playlist {
  id: number;
  name: string;
  is_liked_songs: boolean;
  tracks: Track[] | undefined;
}

function formatDuration(ms: number): string {
  if (!ms) return "0:00";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function totalDuration(tracks: Track[]): string {
  const ms = tracks.reduce((acc, t) => {
    const info = t.track_data?.info ?? t.track_data;
    return acc + (info?.length ?? 0);
  }, 0);
  const totalSeconds = Math.floor(ms / 1000);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// ---------------------------------------------------------------------------
// Create Playlist Modal
// ---------------------------------------------------------------------------
function CreatePlaylistModal({
  onClose,
  onCreated,
  userId,
}: {
  onClose: () => void;
  onCreated: () => void;
  userId: string | number;
}) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    try {
      await createPlaylist(trimmed, userId);
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to create playlist");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-white">New Playlist</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          placeholder="Playlist name..."
          className="w-full bg-neutral-800 border border-neutral-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition mb-2"
        />
        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
        <div className="flex gap-3 mt-4">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg bg-neutral-800 text-gray-400 hover:bg-neutral-700 transition text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={loading || !name.trim()}
            className="flex-1 py-2.5 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold transition text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : null}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import Playlist Modal (SSE-driven)
// ---------------------------------------------------------------------------
function ImportPlaylistModal({
  onClose,
  onImported,
  userId,
}: {
  onClose: () => void;
  onImported: () => void;
  userId: string | number;
}) {
  const [url, setUrl] = useState("");
  const [importStatus, setImportStatus] = useState<"idle" | "importing" | "done" | "error">("idle");
  const [progress, setProgress] = useState({ current: 0, total: 0, trackTitle: "" });
  const [playlistName, setPlaylistName] = useState("");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => inputRef.current?.focus(), []);

  const handleImport = async () => {
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;

    setImportStatus("importing");
    setError("");
    setProgress({ current: 0, total: 0, trackTitle: "" });
    setPlaylistName("");

    try {
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${API_URL}/playlist/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ url: trimmedUrl, user_id: String(userId) }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "start") {
              setPlaylistName(data.playlist_name);
              setProgress({ current: 0, total: data.total, trackTitle: "" });
            } else if (data.type === "track") {
              setProgress({
                current: data.current,
                total: data.total,
                trackTitle: data.track_title,
              });
            } else if (data.type === "done") {
              setPlaylistName(data.playlist_name);
              setProgress((p) => ({ ...p, total: data.total, current: data.total }));
              setImportStatus("done");
              onImported();
            } else if (data.type === "error") {
              setError(data.message);
              setImportStatus("error");
            }
          } catch {
            // ignore malformed SSE frame
          }
        }
      }
    } catch (e: any) {
      setError(e.message || "Import failed. Please try again.");
      setImportStatus("error");
    }
  };

  const progressPct =
    progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-bold text-white">Import Playlist</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Paste a YouTube playlist link to import all tracks
            </p>
          </div>
          {importStatus !== "importing" && (
            <button onClick={onClose} className="text-gray-400 hover:text-white transition">
              <X size={20} />
            </button>
          )}
        </div>

        {/* ── Idle ── */}
        {importStatus === "idle" && (
          <>
            <input
              ref={inputRef}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleImport()}
              placeholder="https://www.youtube.com/playlist?list=..."
              className="w-full bg-neutral-800 border border-neutral-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition mb-4 text-sm"
            />
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 rounded-lg bg-neutral-800 text-gray-400 hover:bg-neutral-700 transition text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                disabled={!url.trim()}
                className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Upload size={16} />
                Start Import
              </button>
            </div>
          </>
        )}

        {/* ── Importing ── */}
        {importStatus === "importing" && (
          <div>
            {playlistName && (
              <p className="text-sm text-gray-300 mb-3">
                Importing{" "}
                <span className="font-semibold text-white">&ldquo;{playlistName}&rdquo;</span>
              </p>
            )}
            {progress.total > 0 ? (
              <>
                <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                  <span className="truncate max-w-[75%]">
                    {progress.trackTitle || "Processing…"}
                  </span>
                  <span className="flex-shrink-0 ml-2">
                    {progress.current} / {progress.total}
                  </span>
                </div>
                <div className="w-full bg-neutral-700 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 text-center">{progressPct}% complete</p>
              </>
            ) : (
              <div className="flex items-center justify-center py-6 text-gray-400">
                <Loader2 size={22} className="animate-spin mr-2" />
                <span className="text-sm">Fetching playlist info…</span>
              </div>
            )}
          </div>
        )}

        {/* ── Done ── */}
        {importStatus === "done" && (
          <div className="text-center py-4">
            <CheckCircle size={44} className="text-green-400 mx-auto mb-3" />
            <p className="text-white font-semibold text-lg">Import Complete!</p>
            <p className="text-sm text-gray-400 mt-1">
              &ldquo;{playlistName}&rdquo; was created with{" "}
              <span className="text-white font-medium">{progress.total}</span> tracks.
            </p>
            <button
              onClick={onClose}
              className="mt-5 px-8 py-2.5 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold transition text-sm"
            >
              Done
            </button>
          </div>
        )}

        {/* ── Error ── */}
        {importStatus === "error" && (
          <div className="text-center py-4">
            <AlertTriangle size={44} className="text-red-400 mx-auto mb-3" />
            <p className="text-white font-semibold">Import Failed</p>
            <p className="text-sm text-gray-400 mt-1 break-words">{error}</p>
            <div className="flex gap-3 mt-5">
              <button
                onClick={() => setImportStatus("idle")}
                className="flex-1 py-2.5 rounded-lg bg-neutral-800 text-gray-400 hover:bg-neutral-700 transition text-sm"
              >
                Try Again
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2.5 rounded-lg bg-neutral-700 text-white hover:bg-neutral-600 transition text-sm"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Track Row
// ---------------------------------------------------------------------------
function TrackRow({
  track,
  index,
  onRemove,
  onPlay,
}: {
  track: Track;
  index: number;
  onRemove: () => void;
  onPlay: () => void;
}) {
  const info = track.track_data?.info ?? track.track_data;
  const [menuOpen, setMenuOpen] = useState(false);
  const title = info?.title ?? "Unknown";
  const author = info?.author ?? "Unknown";
  const length = info?.length ?? 0;

  return (
    <div className="group flex items-center gap-4 px-4 py-2.5 rounded-lg hover:bg-neutral-800/60 transition-colors">
      {/* Index / Play */}
      <div className="w-6 text-center flex-shrink-0">
        <span className="text-sm text-gray-500 group-hover:hidden">{index}</span>
        <button onClick={onPlay} className="hidden group-hover:block">
          <Play size={14} className="text-green-400" />
        </button>
      </div>

      {/* Music icon */}
      <div className="w-9 h-9 rounded-md bg-neutral-700 flex items-center justify-center flex-shrink-0">
        <Music2 size={16} className="text-green-400" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{title}</p>
        <p className="text-xs text-gray-400 truncate">{author}</p>
      </div>

      {/* Duration */}
      <div className="flex items-center gap-1 text-xs text-gray-400 flex-shrink-0">
        <Clock size={12} />
        {formatDuration(length)}
      </div>

      {/* Context menu */}
      <div className="relative flex-shrink-0">
        <button
          onClick={() => setMenuOpen((v) => !v)}
          className="text-gray-500 hover:text-white p-1 rounded opacity-0 group-hover:opacity-100 transition"
        >
          <MoreVertical size={16} />
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-7 bg-neutral-800 border border-neutral-600 rounded-lg shadow-xl z-10 w-36 py-1">
            <button
              onClick={() => {
                setMenuOpen(false);
                onRemove();
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-neutral-700 transition"
            >
              <Trash2 size={14} />
              Remove
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playlist Detail Panel
// ---------------------------------------------------------------------------
interface PlaylistDetailProps {
  playlist: Playlist;
  onBack: () => void;
  onDelete: (id: number) => void;
  onTrackRemoved: () => void;
  userId: string | number;
  selectedGuild: string;
  addToast: (type: ToastType, message: string) => void;
}

function PlaylistDetail({
  playlist,
  onBack,
  onDelete,
  onTrackRemoved,
  userId,
  selectedGuild,
  addToast,
}: PlaylistDetailProps) {
  const [search, setSearch] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [playingAll, setPlayingAll] = useState(false);
  const [showGuildPicker, setShowGuildPicker] = useState(false);
  // pending action to run after guild is picked
  const pendingAction = useRef<(() => void) | null>(null);

  const tracks = playlist.tracks ?? [];
  const filtered = tracks.filter((t) => {
    const info = t.track_data?.info ?? t.track_data;
    return (
      !search ||
      info?.title?.toLowerCase().includes(search.toLowerCase()) ||
      info?.author?.toLowerCase().includes(search.toLowerCase())
    );
  });

  // resolvedGuild: use prop if available, otherwise user picks via modal
  const [localGuild, setLocalGuild] = useState("");
  const activeGuildRef = useRef("");  // kept in sync so pending actions can read it
  const activeGuild = selectedGuild || localGuild;
  activeGuildRef.current = activeGuild;

  const playFromWeb = async (playlistId?: number, trackQuery?: string) => {
    if (!activeGuild) {
      // No guild selected — show picker; retry the action after pick
      pendingAction.current = () => {
        if (playlistId !== undefined) handlePlayAll(playlistId);
        else if (trackQuery) doPlayTrack(trackQuery);
      };
      setShowGuildPicker(true);
      return;
    }
    try {
      const payload: Record<string, unknown> = { guild_id: activeGuildRef.current, user_id: String(userId) };
      if (playlistId !== undefined) payload.playlist_id = playlistId;
      if (trackQuery) payload.track_query = trackQuery;
      await api.post("/bot/play-from-web", payload);
      addToast("success", playlistId ? `▶ Playing playlist "${playlist.name}"` : "▶ Track added to queue");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === "not_in_voice") {
        addToast("warning", "⚠️ You have not joined any voice channel. Join a channel in Discord first!");
      } else {
        addToast("error", detail || "Failed to play. Is the bot online?");
      }
    }
  };

  // Internal helpers split so they can be called after guild pick
  const handlePlayAll = async (pid?: number) => {
    const id = pid ?? playlist.id;
    setPlayingAll(true);
    await playFromWeb(id);
    setPlayingAll(false);
  };

  const doPlayTrack = (query: string) => playFromWeb(undefined, query);

  const handlePlayAllClick = () => handlePlayAll();

  const handleGuildPicked = (guildId: string) => {
    setLocalGuild(guildId);
    activeGuildRef.current = guildId;
    setShowGuildPicker(false);
    if (pendingAction.current) {
      pendingAction.current();
      pendingAction.current = null;
    }
  };

  const handlePlayTrack = (track: Track) => {
    const info = track.track_data?.info ?? track.track_data;
    const title = info?.title;
    const author = info?.author;
    const query = title ? (author ? `${title} ${author}` : title) : "";
    if (query) playFromWeb(undefined, query);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deletePlaylist(playlist.id, userId);
      onDelete(playlist.id);
    } catch {
      setDeleting(false);
    }
  };

  const handleRemoveTrack = async (trackId: number) => {
    try {
      await removeTrackFromPlaylist(playlist.id, trackId);
      onTrackRemoved();
    } catch {
      // silent
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Guild Picker */}
      {showGuildPicker && (
        <GuildPickerModal
          onClose={() => setShowGuildPicker(false)}
          onPick={handleGuildPicked}
        />
      )}
      {/* Header */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4">
        <button
          onClick={onBack}
          className="text-sm text-gray-400 hover:text-white mb-4 flex items-center gap-1 transition"
        >
          ← Back to Playlists
        </button>

        <div className="flex items-start gap-5">
          {/* Cover art */}
          <div className="w-36 h-36 rounded-xl bg-gradient-to-br from-green-700 to-emerald-900 flex items-center justify-center shadow-2xl flex-shrink-0">
            <ListMusic size={56} className="text-white/60" />
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-green-400 mb-1">
              {playlist.is_liked_songs ? "Liked Songs" : "Playlist"}
            </p>
            <h2 className="text-3xl font-black text-white truncate mb-2">{playlist.name}</h2>
            <p className="text-sm text-gray-400">
              {tracks.length} songs
              {tracks.length > 0 && ` • ${totalDuration(tracks)}`}
            </p>

            <div className="flex items-center gap-3 mt-4">
              <button
              onClick={handlePlayAllClick}
                disabled={playingAll || tracks.length === 0}
                className="flex items-center gap-2 bg-green-500 hover:bg-green-600 disabled:opacity-60 text-black font-bold px-5 py-2.5 rounded-full transition text-sm"
              >
                {playingAll ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} fill="currentColor" />}
                Play All
              </button>
              {!playlist.is_liked_songs && (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="flex items-center gap-2 bg-neutral-800 hover:bg-red-900/40 text-gray-400 hover:text-red-400 px-4 py-2.5 rounded-full transition text-sm border border-neutral-700 hover:border-red-800"
                >
                  <Trash2 size={14} />
                  Delete Playlist
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Search bar */}
        {tracks.length > 0 && (
          <div className="relative mt-5">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search in playlist..."
              className="w-full bg-neutral-800/80 border border-neutral-700 rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition"
            />
          </div>
        )}
      </div>

      {/* Track list header */}
      <div className="flex items-center gap-4 px-6 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500 border-b border-neutral-800 flex-shrink-0">
        <span className="w-6 text-center">#</span>
        <span className="w-9" />
        <span className="flex-1">Title</span>
        <span className="flex items-center gap-1"><Clock size={11} /> Duration</span>
        <span className="w-8" />
      </div>

      {/* Track list body */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 py-2">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <Music2 size={48} className="text-neutral-700 mb-3" />
            <p className="text-gray-400 font-medium">
              {search ? "No tracks match your search" : "This playlist is empty"}
            </p>
            <p className="text-sm text-gray-600 mt-1">
              {!search && "Add songs via Discord with /playlist add"}
            </p>
          </div>
        ) : (
          filtered.map((track, i) => (
            <TrackRow
              key={track.id}
              track={track}
              index={i + 1}
              onRemove={() => handleRemoveTrack(track.id)}
              onPlay={() => handlePlayTrack(track)}
            />
          ))
        )}
      </div>

      {/* Delete Confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-700 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
            <h2 className="text-lg font-bold text-white mb-2">Delete "{playlist.name}"?</h2>
            <p className="text-sm text-gray-400 mb-6">
              This will permanently delete the playlist and all its tracks. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(false)}
                className="flex-1 py-2.5 rounded-lg bg-neutral-800 text-gray-400 hover:bg-neutral-700 transition text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold transition text-sm disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playlist Card (grid item)
// ---------------------------------------------------------------------------
function PlaylistCard({
  playlist,
  onClick,
}: {
  playlist: Playlist;
  onClick: () => void;
}) {
  const gradients = [
    "from-green-700 to-emerald-900",
    "from-indigo-700 to-violet-900",
    "from-rose-700 to-pink-900",
    "from-amber-600 to-orange-900",
    "from-cyan-700 to-blue-900",
    "from-teal-700 to-green-900",
  ];
  const gradient = gradients[playlist.id % gradients.length];

  return (
    <button
      onClick={onClick}
      className="group text-left bg-neutral-900/50 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 rounded-xl p-4 transition-all duration-200"
    >
      <div
        className={`w-full aspect-square rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center mb-3 shadow-lg group-hover:shadow-xl transition-shadow`}
      >
        <ListMusic size={36} className="text-white/60" />
      </div>
      <p className="font-semibold text-white truncate text-sm">{playlist.name}</p>
      <p className="text-xs text-gray-400 mt-0.5">
        {playlist.is_liked_songs
          ? "❤️ Liked Songs"
          : `${(playlist.tracks ?? []).length} song${(playlist.tracks ?? []).length !== 1 ? "s" : ""}`}
      </p>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main PlaylistView
// ---------------------------------------------------------------------------
export default function PlaylistView({ selectedGuild = "" }: { selectedGuild?: string }) {
  const user = useAuthStore((s) => s.user);
  const userId = user?.id;

  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlaylist, setSelectedPlaylist] = useState<Playlist | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const toastId = useRef(0);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const removeToast = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const fetchPlaylists = async () => {
    if (!userId) return;
    try {
      const data = await getUserPlaylists(userId);
      // Normalize: ensure every playlist has a tracks array
      const normalized = data.map((p: Playlist) => ({ ...p, tracks: p.tracks ?? [] }));
      setPlaylists(normalized);
      // If viewing a playlist that was updated, refresh it
      if (selectedPlaylist) {
        const refreshed = normalized.find((p: Playlist) => p.id === selectedPlaylist.id);
        if (refreshed) setSelectedPlaylist(refreshed);
        else setSelectedPlaylist(null);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlaylists();
  }, [userId]);

  const handleDeletePlaylist = (id: number) => {
    setPlaylists((prev) => prev.filter((p) => p.id !== id));
    setSelectedPlaylist(null);
  };

  const filtered = playlists.filter((p) =>
    !searchQuery || p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        <Loader2 size={32} className="animate-spin mr-3" />
        <span>Loading playlists...</span>
      </div>
    );
  }

  // Playlist detail view
  if (selectedPlaylist) {
    return (
      <div className="h-full bg-gradient-to-b from-neutral-900 to-[#030202] relative">
        <Toast toasts={toasts} remove={removeToast} />
        <PlaylistDetail
          playlist={selectedPlaylist}
          onBack={() => setSelectedPlaylist(null)}
          onDelete={handleDeletePlaylist}
          onTrackRemoved={fetchPlaylists}
          userId={userId!}
          selectedGuild={selectedGuild}
          addToast={addToast}
        />
      </div>
    );
  }

  // Grid view
  return (
    <div className="flex flex-col h-full p-6">
      <Toast toasts={toasts} remove={removeToast} />
      {showCreate && userId && (
        <CreatePlaylistModal
          userId={userId}
          onClose={() => setShowCreate(false)}
          onCreated={fetchPlaylists}
        />
      )}
      {showImport && userId && (
        <ImportPlaylistModal
          userId={userId}
          onClose={() => setShowImport(false)}
          onImported={fetchPlaylists}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-black text-white">Your Library</h1>
          <p className="text-sm text-gray-400 mt-1">{playlists.length} playlist{playlists.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-600 hover:border-blue-500 text-gray-300 hover:text-blue-400 font-semibold px-4 py-2.5 rounded-full transition text-sm"
          >
            <Upload size={16} />
            Import Playlist
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-green-500 hover:bg-green-600 text-black font-bold px-4 py-2.5 rounded-full transition text-sm"
          >
            <Plus size={18} />
            New Playlist
          </button>
        </div>
      </div>

      {/* Search */}
      {playlists.length > 0 && (
        <div className="relative mb-5 flex-shrink-0">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search playlists..."
            className="w-full bg-neutral-800/60 border border-neutral-700 rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition max-w-sm"
          />
        </div>
      )}

      {/* Grid */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-24 h-24 rounded-2xl bg-neutral-800 flex items-center justify-center mb-4">
              <ListMusic size={40} className="text-neutral-600" />
            </div>
            <h3 className="text-xl font-bold text-gray-300 mb-2">
              {searchQuery ? "No playlists found" : "No playlists yet"}
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              {searchQuery
                ? "Try a different search term"
                : "Create your first playlist and start adding songs."}
            </p>
            {!searchQuery && (
              <button
                onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 bg-green-500 hover:bg-green-600 text-black font-bold px-5 py-2.5 rounded-full transition"
              >
                <Plus size={18} />
                Create Playlist
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {filtered.map((pl) => (
              <PlaylistCard key={pl.id} playlist={pl} onClick={() => setSelectedPlaylist(pl)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
