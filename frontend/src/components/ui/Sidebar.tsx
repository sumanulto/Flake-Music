import { Music2, Server, Settings } from "lucide-react";
import type { ReactNode } from "react";
import type { Player } from "@/types/player";

interface Stat {
  icon: ReactNode;
  value: string;
  className?: string;
  label?: string;
}

interface SidebarProps {
  isSidebarOpen: boolean;
  activeView: string;
  setActiveView: (view: string) => void;
  players: Player[];
  selectedGuild: string;
  setSelectedGuild: (guildId: string) => void;
  getServerName: (guildId: string) => string;
  botStatus: any;
  stats: Stat[];
  onLogout: () => void;
}

export default function Sidebar({
  isSidebarOpen,
  activeView,
  setActiveView,
  players,
  selectedGuild,
  setSelectedGuild,
  getServerName,
  stats,
}: SidebarProps) {

  const navButtonBase =
    "transition-colors rounded-md flex items-center justify-center p-2";
  const activeStyle = "bg-stone-700 text-white";
  const inactiveStyle = "text-gray-300 hover:bg-neutral-800 hover:text-white";

  if (!isSidebarOpen) {
    return (
      <aside className="w-20 border-r border-stone-800 relative flex flex-col items-center py-4">
        {/* Collapsed Nav */}
        <nav className="flex flex-col gap-2 w-full px-2">
          {[
            { label: "Player", icon: <Music2 />, view: "player" },
            { label: "Servers", icon: <Server />, view: "servers" },
            { label: "Settings", icon: <Settings />, view: "settings" },
          ].map(({ label, icon, view }) => (
            <button
              key={view}
              aria-label={label}
              onClick={() => setActiveView(view)}
              className={`${navButtonBase} flex-col ${
                activeView === view ? activeStyle : inactiveStyle
              }`}
            >
              {icon}
              <span className="text-[10px] mt-1">{label}</span>
            </button>
          ))}
        </nav>

        {/* Active Servers (Collapsed) */}
        <div className="px-2 mt-4 w-full">
          <h3 className="text-xs font-semibold text-gray-400 text-center mb-3 uppercase tracking-wider">
            Active
          </h3>
          <div className="space-y-2">
            {players.map((player) => (
              <button
                key={player.guildId}
                onClick={() => setSelectedGuild(player.guildId)}
                className={`w-full px-1 py-2 rounded-md flex flex-col items-center justify-center transition-colors ${
                  selectedGuild === player.guildId
                    ? "text-slate-50 bg-green-700"
                    : "text-gray-300 hover:bg-gray-800"
                }`}
              >
                {player.playing && (
                  <div className="flex space-x-1 mt-1 h-4 items-end">
                    {[0, 0.2, 0.4].map((delay, i) => (
                      <div
                        key={i}
                        className="w-1 bg-white rounded-sm animate-bar"
                        style={{
                          animationDelay: `${delay}s`,
                          animationDuration: "1s",
                          animationIterationCount: "infinite",
                          transformOrigin: "bottom", // critical for bottom growth
                        }}
                      />
                    ))}
                  </div>
                )}

                <span className="text-[9px] text-center truncate w-full mt-1">
                  {getServerName(player.guildId)}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Collapsed Stats */}
        <div className="px-2 pb-4 border-t border-stone-800 pt-4 absolute bottom-0 ">
          <div className="flex flex-col justify-center item-center gap-4 text-sm text-gray-100">
            {stats.map((item, i) => (
              <div key={i} className="relative justify-center">
                <div className="text-gray-400">{item.icon}</div>
                <div
                  className={`absolute -top-2 -right-2 bg-neutral-50 text-neutral-900 font-extrabold text-xs px-1.5 py-0.5 rounded-full border border-black ${
                    item.className || ""
                  }`}
                >
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>
    );
  }

  // Expanded Sidebar
  return (
    <aside className="w-64  border-r border-stone-800 flex flex-col">
      {/* Navigation */}
      <nav className="space-y-1 px-2 pt-4">
        {[
          { label: "Player", icon: <Music2 size={20} />, view: "player" },
          { label: "Servers", icon: <Server size={20} />, view: "servers" },
          { label: "Settings", icon: <Settings size={20} />, view: "settings" },
        ].map(({ label, icon, view }) => (
          <button
            key={view}
            aria-label={label}
            onClick={() => setActiveView(view)}
            className={`w-full text-left px-3 py-2 rounded transition-colors flex items-center space-x-3 ${
              activeView === view ? activeStyle : inactiveStyle
            }`}
          >
            {icon}
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="border-t border-stone-800 my-4" />

      {/* Active Servers */}
      <div className="px-4 flex-1 overflow-y-auto custom-scrollbar">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Active Servers
        </h3>
        <div className="space-y-2">
          {players.map((player) => (
            <button
              key={player.guildId}
              onClick={() => {
                setSelectedGuild(player.guildId);
                setActiveView("player");
              }}
              className={`w-full text-left p-3 rounded-md transition-colors ${
                selectedGuild === player.guildId
                  ? "text-slate-50 bg-green-600"
                  : "bg-neutral-800 hover:bg-neutral-700 text-gray-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 min-w-0">
                  <Server className="h-4 w-4 flex-shrink-0" />
                  <span className="text-sm font-medium truncate">
                    {getServerName(player.guildId)}
                  </span>
                </div>
                {player.playing && (
                  <div className="flex space-x-1 mt-1 h-4 items-end">
                    {[0, 0.2, 0.4].map((delay, i) => (
                      <div
                        key={i}
                        className="w-1 bg-white rounded-sm animate-bar"
                        style={{
                          animationDelay: `${delay}s`,
                          animationDuration: "1s",
                          animationIterationCount: "infinite",
                          transformOrigin: "bottom", // critical for bottom growth
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
              {player.current && (
                <div className="mt-2 text-xs text-gray-200 truncate">
                  {player.current.title}
                </div>
              )}
            </button>
          ))}
        </div>

        {players.length === 0 && (
          <div className="text-center py-8">
            <Server className="h-8 w-8 mx-auto text-gray-600 mb-2" />
            <p className="text-sm text-gray-500">No active servers</p>
          </div>
        )}
      </div>

      <div className="border-t border-stone-800 my-4" />

      {/* Stats */}
      <div className="px-4 space-y-3 pb-4">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide text-center">
          Statistics
        </h3>
        <div className="grid grid-cols-2 gap-3 w-full">
          {stats.map((stat, index) => (
            <div key={index} className="bg-neutral-800 rounded-lg p-3">
              <div
                className={`flex flex-col items-center justify-center space-y-2 ${
                  stat.className || "text-gray-300"
                }`}
              >
                <div className="text-xs text-gray-400">{stat.label}</div>
                <div className="flex items-center justify-between w-full px-2 ">
                  <div className="h-5 w-5 text-gray-300">{stat.icon}</div>
                  <p className="text-sm font-semibold">{stat.value}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
