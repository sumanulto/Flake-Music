import { useState, useEffect, useRef } from "react";
import Sidebar from "@/components/ui/Sidebar";
import PlayerCard from "@/components/ui/PlayerCard";
import SettingsView from "@/components/views/SettingsView";
import PlaylistView from "@/components/views/PlaylistView";
import {
  Music,
  Server,
  AlertCircle,
  RotateCcw,
  Menu,
  Music2,
  Cpu,
  Users,
  Bot,
  SquareTerminal,
  BadgeCheck,
  BadgeX,
  Triangle,
  X,
  LogOut,
  Settings,
  Lock,
  ShieldAlert,
} from "lucide-react";
import { Player } from "@/types/player";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/useAuthStore";

interface BotStatus {
  botOnline: boolean;
  version?: string;
  latency?: number;
  guilds: number;
  users: number;
  players: number;
  system?: {
    cpu_pct: number;
    ram_used_gb: number;
    ram_total_gb: number;
    ram_pct: number;
    disk_used_gb: number;
    disk_total_gb: number;
    disk_pct: number;
  };
  nodes: Array<{
    identifier: string;
    connected: boolean;
    address?: string;
    stats: {
      players: number;
      cpu_pct: number;
      ram_used_mb: number;
      ram_total_mb: number;
      ram_pct: number;
      uptime: string;
      latency_ms: number;
    } | null;
  }>;
}

export default function Dashboard() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedGuild, setSelectedGuild] = useState<string>("");
  // Maps guildId -> whether the logged-in user is in that guild's voice channel
  const [userVoiceGuilds, setUserVoiceGuilds] = useState<Record<string, boolean>>({});

  const selectedGuildRef = useRef(selectedGuild);

  useEffect(() => {
    selectedGuildRef.current = selectedGuild;
  }, [selectedGuild]);

  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [activeView, setActiveView] = useState("player");
  const restartingBot = false;
  const [volume, setVolume] = useState(100);

  const [isMuted, setIsMuted] = useState(false);
  const [isSeekingTimeline, setIsSeekingTimeline] = useState(false);
  const [isStateButtonOpen, setIsStateButtonOpen] = useState(false);
  const [showTerminalDialog, setShowTerminalDialog] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState("");
  const [loadingTerminal, setLoadingTerminal] = useState(false);

  useEffect(() => {
    fetchBotStatus();
    fetchPlayers();

    const interval = setInterval(() => {
      if (!isSeekingTimeline) {
        fetchBotStatus();
        fetchPlayers(selectedGuildRef.current);
      }
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSeekingTimeline]);

  const fetchBotStatus = async () => {
    try {
      const response = await api.get("/bot/status");
      const data = response.data;
      setBotStatus(data);
      if (data.error && !data.botOnline) {
        setError(data.error);
      } else {
        setError("");
      }
    } catch (error) {
      console.error("Failed to fetch bot status:", error);
      setError("Failed to connect to bot API");
    }
  };

  const fetchPlayers = async (currentGuildIdFromRef?: string) => {
    try {
      const response = await api.get("/bot/players");
      const data: Player[] = response.data;
      setPlayers(data);

      const guildIdToUse =
        currentGuildIdFromRef !== undefined
          ? currentGuildIdFromRef
          : selectedGuild;
      const currentPlayer = data.find((p) => p.guildId === guildIdToUse);
      if (currentPlayer && typeof currentPlayer.volume === "number") {
        setVolume(currentPlayer.volume);
      }

      const currentSelectedGuildExists = data.some(
        (p) => p.guildId === guildIdToUse
      );

      if (!guildIdToUse || !currentSelectedGuildExists) {
        if (data.length > 0) {
          setSelectedGuild(data[0].guildId);
        } else {
          setSelectedGuild("");
        }
      }

      // ── Voice-channel check for every active guild ──────────────────────
      if (user?.id && data.length > 0) {
        const checks = await Promise.allSettled(
          data.map((p) =>
            api
              .get("/bot/voice-check", {
                params: { guild_id: p.guildId, user_id: user.id },
              })
              .then((r) => ({ guildId: p.guildId, inVoice: !!r.data?.in_voice }))
              .catch(() => ({ guildId: p.guildId, inVoice: false }))
          )
        );
        const map: Record<string, boolean> = {};
        for (const result of checks) {
          if (result.status === "fulfilled") {
            map[result.value.guildId] = result.value.inVoice;
          }
        }
        setUserVoiceGuilds(map);
      }
      // ────────────────────────────────────────────────────────────────────
    } catch (error) {
      console.error("Failed to fetch players:", error);
    }
  };

  const controlPlayer = async (action: string, options: { query?: string, index?: number, enabled?: boolean, mode?: string } = {}) => {
    if (!selectedGuild) return;

    setLoading(true);
    try {
      await api.post("/bot/control", { 
          action, 
          guildId: selectedGuild, 
          ...options
      });
      
      if (action === "play") {
          fetchPlayers();
      } else {
          setTimeout(fetchPlayers, 500); 
      }

      if (action === "seek" && options.query !== undefined) {
        const newPosition = parseInt(options.query, 10);
        setPlayers((prevPlayers) =>
          prevPlayers.map((player) =>
            player.guildId === selectedGuild
              ? { ...player, position: newPosition }
              : player
          )
        );
      }
    } catch (error) {
      console.error("Failed to control player:", error);
      setError("Failed to control player");
    } finally {
      setLoading(false);
    }
  };

  const seekToPosition = async (percentage: number) => {
    if (!currentPlayer?.current || typeof currentPlayer.current.duration !== "number") return;
    const newPosition = Math.floor(
      (percentage / 100) * currentPlayer.current.duration
    );
    await controlPlayer("seek", { query: newPosition.toString() });
  };


  const handleVolumeChange = (newVolume: number) => {
    controlPlayer("volume", { query: newVolume.toString() });
  };

  const toggleMute = () => {
    if (isMuted) {
      setIsMuted(false);
      controlPlayer("volume", { query: volume.toString() });
    } else {
      setIsMuted(true);
      controlPlayer("volume", { query: "0" });
    }
    setTimeout(fetchPlayers, 300);
  };

  const formatTime = (ms: number) => {
    if (!ms || isNaN(ms)) return "0:00";
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  const stats = [
    {
      label: "Servers",
      value: String(botStatus?.guilds || 0),
      icon: <Server />,
    },
    {
      label: "Users",
      value: String(botStatus?.users || 0),
      icon: <Users />,
    },
    {
      label: "Players",
      value: String(botStatus?.players || 0),
      icon: <Music2 />,
    },
    {
      label: "Nodes",
      value: String(
        (botStatus?.nodes || []).filter((n: { connected: boolean }) => n.connected)
          .length || 0
      ),
      icon: <Cpu />,
      className: (botStatus?.nodes || []).some(
        (n: { connected: boolean }) => n.connected
      )
        ? "text-green-400"
        : "text-red-400",
    },
  ];

  const currentPlayer = players.find((p) => p.guildId === selectedGuild);

  useEffect(() => {
    if (showTerminalDialog) fetchTerminalOutput();
  }, [showTerminalDialog]);

  const fetchTerminalOutput = async () => {
    setLoadingTerminal(true);
    try {
      // api.get("/bot/terminal")...
      setTerminalOutput("Terminal output not implemented.");
    } catch {
      setTerminalOutput("Failed to load terminal output.");
    } finally {
      setLoadingTerminal(false);
    }
  };

  const getStatusIcon = () => {
    if (showTerminalDialog) {
      return <SquareTerminal className="h-3.5 w-3.5 text-purple-400" />;
    } else if (restartingBot) {
      return ( <RotateCcw className="h-3.5 w-3.5 text-yellow-400 animate-spin-reverse"/>);
    } else if (botStatus?.botOnline) {
      return <BadgeCheck className="h-3.5 w-3.5 text-green-500" />;
    } else {
      return <BadgeX className="h-3.5 w-3.5 text-red-500" />;
    }
  };

  if (!botStatus) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#030202] text-white">
        <div className="text-center">
          <Music className="h-16 w-16 mx-auto mb-4 text-gray-500" />
          <h1 className="text-2xl font-semibold">Loading...</h1>
          <p className="text-gray-400">Connecting to the bot...</p>
        </div>
      </div>
    );
  }

  const performSearch = async (query: string) => {
    if (!selectedGuild || !query) return [];
    try {
        const res = await api.get("/bot/search", { params: { query, guildId: selectedGuild } });
        return res.data;
    } catch (e) {
        console.error("Search failed", e);
        return [];
    }
  };

  return (
    <div className="min-h-screen bg-[#030202] text-white overflow-hidden">
      {/* Header */}
      <header className="border-b h-20 border-stone-800 px-6 flex items-center">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center space-x-4 gap-4">
            <div
              className="hover:bg-neutral-800 rounded p-2 cursor-pointer border-neutral-800 border"
              onClick={() => setIsSidebarOpen((prev) => !prev)}
            >
              <Menu className="h-5 w-5 text-slate-300" />
            </div>
            <div className="flex items-center space-x-2">
              <img src="/logo.gif" alt="Flake Music" className="h-10 w-10 object-contain" />
              <h1 className="text-2xl font-bold">Flake Music</h1>
            </div>
          </div>

          {/* Right Side Controls */}
          <div className="flex items-center gap-4">
              {/* Bot Controls */}
              <div
                className="relative"
                onMouseEnter={() => setIsStateButtonOpen(true)}
                onMouseLeave={() => setIsStateButtonOpen(false)}
              >
                <div className="relative cursor-pointer bg-stone-600 p-2 rounded-full hover:bg-stone-700 transition">
                  <Bot className="h-6 w-6 text-gray-300" />

                  {/* Status Badge */}
                  <div className="absolute -top-1 -right-1 bg-stone-900 rounded-full p-0.5 border border-stone-600">
                    {getStatusIcon()}
                  </div>
                </div>

                {/* Status Panel */}
                {isStateButtonOpen && (
                  <div className="absolute right-0 mt-2 z-50 w-72">
                    {/* caret */}
                    <div className="w-full flex justify-end pr-3">
                      <Triangle className="h-3 w-3 fill-neutral-900 text-neutral-900" />
                    </div>
                    <div className="bg-neutral-900 border border-neutral-700 rounded-lg shadow-2xl font-mono text-xs text-green-400 p-4 space-y-3">
                      {/* System Info */}
                      <div>
                        <p className="text-neutral-500 uppercase tracking-widest text-[10px] mb-1">== System Info ==</p>
                        <p>• CPU:  <span className="text-white">{botStatus?.system?.cpu_pct ?? "–"}%</span></p>
                        <p>• RAM:  <span className="text-white">{botStatus?.system?.ram_used_gb ?? "–"}/{botStatus?.system?.ram_total_gb ?? "–"}GB</span> <span className="text-neutral-400">({botStatus?.system?.ram_pct ?? "–"}%)</span></p>
                        <p>• DISK: <span className="text-white">{botStatus?.system?.disk_used_gb ?? "–"}/{botStatus?.system?.disk_total_gb ?? "–"}GB</span> <span className="text-neutral-400">({botStatus?.system?.disk_pct ?? "–"}%)</span></p>
                      </div>

                      <div className="border-t border-neutral-700" />

                      {/* Bot Info */}
                      <div>
                        <p className="text-neutral-500 uppercase tracking-widest text-[10px] mb-1">Bot Information</p>
                        <p>• VERSION: <span className="text-white">{botStatus?.version ?? "–"}</span></p>
                        <p>• LATENCY: <span className="text-white">{botStatus?.latency ?? "–"}ms</span></p>
                        <p>• GUILDS:  <span className="text-white">{botStatus?.guilds ?? 0}</span></p>
                        <p>• USERS:   <span className="text-white">{botStatus?.users ?? 0}</span></p>
                        <p>• PLAYERS: <span className="text-white">{botStatus?.players ?? 0}</span></p>
                      </div>

                      {/* Nodes */}
                      {(botStatus?.nodes ?? []).map((node) => (
                        <div key={node.identifier} className="border-t border-neutral-700 pt-3">
                          <p className="text-neutral-500 uppercase tracking-widest text-[10px] mb-1">
                            <span className={node.connected ? "text-green-500" : "text-red-500"}>●</span>
                            {" "}{node.identifier} Node — {node.connected ? "Connected" : "Disconnected"}
                          </p>
                          {node.stats ? (
                            <>
                              <p>• ADDRESS: <span className="text-white">{node.address ?? "–"}</span></p>
                              <p>• PLAYERS: <span className="text-white">{node.stats.players}</span></p>
                              <p>• CPU:     <span className="text-white">{node.stats.cpu_pct}%</span></p>
                              <p>• RAM:     <span className="text-white">{node.stats.ram_used_mb}/{node.stats.ram_total_mb}MB</span> <span className="text-neutral-400">({node.stats.ram_pct}%)</span></p>
                              <p>• LATENCY: <span className="text-white">{node.stats.latency_ms}ms</span></p>
                              <p>• UPTIME:  <span className="text-white">{node.stats.uptime}</span></p>
                            </>
                          ) : (
                            <>
                              <p>• ADDRESS: <span className="text-white">{node.address ?? "–"}</span></p>
                              <p className="text-neutral-500 italic">No stats available</p>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Settings Button */}
              <button
                onClick={() => setActiveView("settings")}
                className={`p-2 rounded-full transition-colors border ${
                  activeView === "settings"
                    ? "bg-neutral-700 border-neutral-600 text-white"
                    : "bg-neutral-900/50 border-neutral-800 text-gray-400 hover:text-white hover:bg-neutral-800"
                }`}
                title="Settings"
              >
                <Settings className="h-5 w-5" />
              </button>

              {/* Logout Button */}
              <button
                onClick={handleLogout}
                className="bg-red-900/20 hover:bg-red-900/40 text-red-500 hover:text-red-400 p-2 rounded-full transition-colors border border-red-900/50"
                title="Logout"
              >
                <LogOut className="h-5 w-5" />
              </button>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-80px)]">
        {/* Sidebar */}
        <Sidebar
          isSidebarOpen={isSidebarOpen}
          activeView={activeView}
          setActiveView={setActiveView}
          players={players}
          selectedGuild={selectedGuild}
          setSelectedGuild={setSelectedGuild}
          stats={stats}
          onLogout={handleLogout}
        />
        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {error && (
            <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 mx-6 mt-4 rounded-lg">
              <div className="flex items-center">
                <AlertCircle className="h-5 w-5 mr-2" />
                <span>{error}</span>
              </div>
            </div>
          )}

          {activeView === "player" && (
                 <div className="flex-1 overflow-hidden p-6 relative">
                    <div className="absolute inset-0 bg-linear-to-b from-green-900/10 to-transparent pointer-events-none" />

                    {players.find((p) => p.guildId === selectedGuild) ? (
                      // ── Voice-channel guard ──────────────────────────────
                      userVoiceGuilds[selectedGuild] === false ? (
                        <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                          <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-2xl p-8 max-w-md">
                            <ShieldAlert className="h-14 w-14 mx-auto mb-4 text-yellow-500" />
                            <h3 className="text-xl font-semibold text-yellow-300 mb-2">Access Restricted</h3>
                            <p className="text-yellow-200/70 text-sm">
                              You're not in this server's voice channel.<br />
                              Join the voice channel in Discord first to control this player.
                            </p>
                          </div>
                        </div>
                      ) : (
                      // ── Normal player ────────────────────────────────────
                        <PlayerCard
                          currentPlayer={players.find((p) => p.guildId === selectedGuild)!}
                          controlPlayer={controlPlayer}
                          formatTime={formatTime}
                          isMuted={isMuted}
                          toggleMute={toggleMute}
                          volume={volume}
                          setVolume={handleVolumeChange}
                          loading={loading}
                          seekToPosition={seekToPosition}
                          setIsSeekingTimeline={setIsSeekingTimeline}
                          selectedGuild={selectedGuild}
                          isSeekingTimeline={isSeekingTimeline}
                          performSearch={performSearch}
                        />
                      )
                    ) : (
                      <div className="flex items-center justify-center h-full text-gray-500">
                        {selectedGuild ? "No player active for this guild" : "Select a guild to view player"}
                      </div>
                    )}
                 </div>
             )}
             
             {activeView === "settings" && (
                 <div className="flex-1 overflow-y-auto">
                    <SettingsView />
                 </div>
             )}

             {activeView === "playlists" && (
                 <div className="flex-1 overflow-hidden">
                    <PlaylistView selectedGuild={selectedGuild} />
                 </div>
             )}

          {activeView === "servers" && (
            <div className="flex-1 p-6 overflow-y-auto">
              <h2 className="text-2xl font-bold mb-6">Server Management</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {players.map((player) => (
                  <div
                    key={player.guildId}
                    className="bg-neutral-800 rounded-lg p-6 border border-stone-800"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex flex-col min-w-0 mr-2">
                        <h3 className="text-lg font-semibold truncate">
                          {player.guildName || `Server ${player.guildId.slice(-4)}`}
                        </h3>
                        <span className="text-xs text-gray-400 mt-0.5 flex items-center gap-1 truncate">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-gray-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                          {player.voiceChannel}
                        </span>
                      </div>
                      <span
                        className={`px-2 py-1 rounded-full text-xs shrink-0 ${
                          player.connected
                            ? "bg-green-900 text-green-300"
                            : "bg-red-900 text-red-300"
                        }`}
                      >
                        {player.connected ? "Connected" : "Disconnected"}
                      </span>
                    </div>

                    {player.current && (
                      <div className="mb-4">
                        <div className="flex items-center space-x-3">
                          <img
                            src={player.current.thumbnail || "/placeholder.svg"}
                            alt="Track"
                            className="w-12 h-12 rounded object-cover"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                              {player.current.title}
                            </p>
                            <p className="text-xs text-gray-400 truncate">
                              {player.current.author}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="space-y-2 text-sm text-gray-400">
                      <div className="flex justify-between">
                        <span>Status:</span>
                        <span
                          className={
                            player.playing ? "text-green-400" : "text-gray-400"
                          }
                        >
                          {player.playing
                            ? "Playing"
                            : player.paused
                            ? "Paused"
                            : "Stopped"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Queue:</span>
                        <span>{player.queue.length} songs</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Volume:</span>
                        <span>{player.volume}%</span>
                      </div>
                    </div>

                    {userVoiceGuilds[player.guildId] === false ? (
                      // ── User NOT in this voice channel ───────────────────
                      <div className="mt-4">
                        <button
                          disabled
                          className="w-full px-4 py-2 bg-neutral-700 text-neutral-500 rounded-lg flex items-center justify-center gap-2 cursor-not-allowed"
                        >
                          <Lock className="h-4 w-4" />
                          Control Player
                        </button>
                        <p className="mt-2 text-xs text-yellow-500/80 flex items-center gap-1 justify-center">
                          <ShieldAlert className="h-3.5 w-3.5" />
                          You're not in this voice channel
                        </p>
                      </div>
                    ) : (
                      // ── User IS in this voice channel (or state unknown) ─
                      <button
                        onClick={() => {
                          setSelectedGuild(player.guildId);
                          setActiveView("player");
                        }}
                        className="w-full mt-4 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                      >
                        Control Player
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {players.length === 0 && (
                <div className="text-center py-12">
                  <Server className="h-16 w-16 mx-auto text-gray-600 mb-4" />
                  <h3 className="text-xl font-semibold text-gray-300 mb-2">
                    No Active Servers
                  </h3>
                  <p className="text-gray-500">
                    Start playing music in Discord to see servers here
                  </p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>

     {/* Simple Terminal Modal */}
      {showTerminalDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-[#18181b] w-full max-w-2xl rounded-lg border border-neutral-700 shadow-xl overflow-hidden m-4">
                <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-700 bg-neutral-900">
                    <h3 className="font-semibold text-lg text-white">Bot Terminal Output</h3>
                    <button onClick={() => setShowTerminalDialog(false)} className="text-gray-400 hover:text-white">
                        <X size={20} />
                    </button>
                </div>
                <div className="p-4 bg-black overflow-auto h-75 font-mono text-xs text-green-400 whitespace-pre-wrap">
                    {loadingTerminal ? "Loading..." : terminalOutput}
                </div>
            </div>
        </div>
      )}

      <style>{`
        .slider::-webkit-slider-thumb {
          appearance: none;
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: #16a34a;
          cursor: pointer;
          box-shadow: 0 0 2px 0 #000;
        }

        .slider::-moz-range-thumb {
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: #16a34a;
          cursor: pointer;
          border: none;
          box-shadow: 0 0 2px 0 #000;
        }
      `}</style>
    </div>
  );
}
