import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Plus, Trash2, ShieldAlert } from "lucide-react";

interface AllowedUser {
    id: number;
    discord_id: string; // Changed to string
    username: string | null;
}


interface AllowedGuild {
    id: number;
    guild_id: string; // Changed to string
    name: string | null;
}

export default function SettingsView() {
    const [users, setUsers] = useState<AllowedUser[]>([]);
    const [newUserState, setNewUserState] = useState({ discord_id: "", username: "" });
    const [loading, setLoading] = useState(true); // Start loading true
    const [error, setError] = useState("");
    
    // Guild State
    const [guilds, setGuilds] = useState<AllowedGuild[]>([]);
    const [newGuildState, setNewGuildState] = useState({ guild_id: "", name: "" });
    
    // We can try to fetch. If 403, we know we aren't admin.
    const [isAdmin, setIsAdmin] = useState(true); 

    // Invite Modal State
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [userGuilds, setUserGuilds] = useState<any[]>([]);

    const fetchUserGuilds = async () => {
        try {
            const res = await api.get("/auth/guilds");
            setUserGuilds(res.data);
        } catch (err) {
            console.error("Failed to fetch user guilds", err);
        }
    };

    useEffect(() => {
       if (showInviteModal) {
           fetchUserGuilds();
       }
    }, [showInviteModal]);

    const fetchUsers = async () => {
        try {
            const res = await api.get("/users/");
            setUsers(res.data);
        } catch (err: any) {
            console.error("Failed to fetch users", err);
             // We don't necessarily want to set isAdmin false here if it was just a network error,
             // but 403 definitely means not admin.
            if (err.response?.status === 403) setIsAdmin(false);
        }
    };

    const fetchGuilds = async () => {
        try {
            const res = await api.get("/allowed-guilds/");
            setGuilds(res.data);
        } catch (err: any) {
             console.error("Failed to fetch guilds", err);
             if (err.response?.status === 403) setIsAdmin(false);
        }
    }; 

    useEffect(() => {
        let mounted = true;

        const loadData = async () => {
            setLoading(true);
            try {
                // Parallel fetch
                const [usersRes, guildsRes] = await Promise.allSettled([
                    api.get("/users/"),
                    api.get("/allowed-guilds/")
                ]);

                if (mounted) {
                    // Handle Users
                    if (usersRes.status === 'fulfilled') {
                         setUsers(usersRes.value.data);
                         setIsAdmin(true); // Default to true if success
                    } else {
                        console.error("Failed to fetch users", usersRes.reason);
                        if (usersRes.reason.response?.status === 403) {
                             setIsAdmin(false);
                        }
                    }

                    // Handle Guilds 
                    // (Only valid if we are admin, but 403 on users usually implies 403 on guilds)
                    if (guildsRes.status === 'fulfilled') {
                        setGuilds(guildsRes.value.data);
                    } else {
                         console.error("Failed to fetch guilds", guildsRes.reason);
                         if (guildsRes.reason.response?.status === 403) {
                             setIsAdmin(false);
                        }
                    }
                }
            } catch (e) {
                console.error("Critical error loading settings", e);
                setError("Failed to load settings.");
            } finally {
                if (mounted) setLoading(false);
            }
        };
        
        loadData();
        
        return () => { mounted = false; };
    }, []);

    const handleAddUser = async () => {
        if (!newUserState.discord_id) return;
        try {
            await api.post("/users/", { 
                discord_id: newUserState.discord_id, // Send as string
                username: newUserState.username || "Unknown" 
            });
            setNewUserState({ discord_id: "", username: "" });
            fetchUsers();
        } catch (err) {
            console.error("Failed to add user", err);
            setError("Failed to add user. Check ID format.");
        }
    };

    const handleRemoveUser = async (discordId: string) => {
        if(!confirm("Are you sure?")) return;
        try {
            await api.delete(`/users/${discordId}`);
            fetchUsers();
        } catch (err) {
            console.error("Failed to remove user", err);
        }
    };

    const handleAddGuild = async () => {
        if (!newGuildState.guild_id) return;
        try {
            await api.post("/allowed-guilds/", { 
                guild_id: newGuildState.guild_id, // Send as string
                name: newGuildState.name || "Unknown Server" 
            });
            setNewGuildState({ guild_id: "", name: "" });
            fetchGuilds();
        } catch (err) {
            console.error("Failed to add guild", err);
            setError("Failed to add guild. Check ID format.");
        }
    };

    const handleRemoveGuild = async (guildId: string) => {
        if(!confirm("Are you sure? The bot will leave this guild if it's currently in it (on next check).")) return;
        try {
            await api.delete(`/allowed-guilds/${guildId}`);
            fetchGuilds();
        } catch (err) {
            console.error("Failed to remove guild", err);
        }
    };

    if (loading) {
        return (
             <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <p>Loading settings...</p>
            </div>
        )
    }

    if (!isAdmin) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <ShieldAlert className="h-16 w-16 mb-4 text-red-500" />
                <h2 className="text-xl font-semibold text-white">Access Denied</h2>
                <p>Only the Super Admin can manage settings.</p>
            </div>
        );
    }

    const handleInvite = async (guild: any) => {
        // 1. Add to allowed list
        try {
            await api.post("/allowed-guilds/", {
                guild_id: guild.id, // Send as string (guild.id from Discord API is string)
                name: guild.name
            });
            fetchGuilds(); // Refresh list
        } catch (err: any) {
            console.error("Failed to add guild", err);
            // Verify if error is just "already exists", if so continue
        }
        
        // 2. Open Invite Window
        const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID; // Ensure this is set in .env
        const permissions = "8"; // Administrator
        const scope = "bot%20applications.commands";
        
        const inviteUrl = `https://discord.com/oauth2/authorize?client_id=${clientId}&permissions=${permissions}&scope=${scope}&guild_id=${guild.id}&disable_guild_select=true`;
        
        window.open(inviteUrl, "_blank", "width=500,height=800");
        setShowInviteModal(false);
    };

    console.log("SettingsView Render:", { isAdmin, loading, usersCount: users?.length, guildsCount: guilds?.length, usersData: users, guildsData: guilds });

    return (
        <div className="p-8 max-w-4xl mx-auto w-full relative">
            <h1 className="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">
                Settings & User Management
            </h1>

            {/* Allowed Users Section */}
            <div className="bg-neutral-900 rounded-lg p-6 border border-neutral-800 mb-8">
                <h2 className="text-xl font-semibold text-green-500 mb-4">Allowed Users</h2>
                <p className="text-gray-400 text-sm mb-6">
                    Manage users who are allowed to access this dashboard. The Super Admin ID is set in the environment variables and has permanent access.
                </p>

                {/* Add User Form */}
                <div className="flex gap-4 mb-8 bg-neutral-950 p-4 rounded-md items-end">
                    <div className="flex-1">
                        <label className="block text-xs text-gray-500 mb-1">Discord User ID</label>
                        <input 
                            type="text" 
                            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-white text-sm focus:border-green-600 outline-none"
                            placeholder="e.g. 123456789012345678"
                            value={newUserState.discord_id}
                            onChange={(e) => setNewUserState({...newUserState, discord_id: e.target.value})}
                        />
                    </div>
                    <div className="flex-1">
                        <label className="block text-xs text-gray-500 mb-1">Username (Optional)</label>
                        <input 
                            type="text" 
                            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-white text-sm focus:border-green-600 outline-none"
                            placeholder="e.g. JohnDoe"
                            value={newUserState.username}
                            onChange={(e) => setNewUserState({...newUserState, username: e.target.value})}
                        />
                    </div>
                    <button 
                        onClick={handleAddUser}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded flex items-center gap-2 h-10 transition-colors"
                    >
                        <Plus size={18} />
                        Add
                    </button>
                </div>

                {/* User List */}
                <div className="space-y-2">
                    {(!users || users.length === 0) && !loading && (
                        <div className="text-center text-gray-500 py-4">No allowed users found.</div>
                    )}
                    {Array.isArray(users) && users.map((u, idx) => {
                        if (!u) return null; // Skip nulls
                        return (
                        <div key={u.id || idx} className="flex items-center justify-between p-3 bg-neutral-800 rounded border border-neutral-700">
                            <div className="flex items-center gap-3">
                                <div className="h-8 w-8 rounded-full bg-green-900 flex items-center justify-center text-green-300 font-bold text-xs">
                                    {u.username && u.username.length > 0 ? u.username[0].toUpperCase() : "U"}
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-white">{u.username || "Unknown"}</p>
                                    <p className="text-xs text-gray-500 font-mono">{u.discord_id}</p>
                                </div>
                            </div>
                            <button 
                                onClick={() => u.discord_id && handleRemoveUser(u.discord_id)}
                                className="text-red-400 hover:text-red-300 hover:bg-red-900/20 p-2 rounded transition-colors"
                                title="Remove User"
                            >
                                <Trash2 size={18} />
                            </button>
                        </div>
                    )})} 
                </div>
            </div>

            {/* Allowed Guilds Section */}
            <div className="bg-neutral-900 rounded-lg p-6 border border-neutral-800 mb-20">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-semibold text-blue-500">Allowed Guilds (Servers)</h2>
                    <button 
                        onClick={() => setShowInviteModal(true)}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded flex items-center gap-2 text-sm transition-colors"
                    >
                        <Plus size={16} />
                        Invite Bot
                    </button>
                </div>
                <p className="text-gray-400 text-sm mb-6">
                    Manage servers where the bot is allowed to join. If the bot joins a server not in this list, it will automatically leave.
                </p>

                {/* Add Guild Form */}
                <div className="flex gap-4 mb-8 bg-neutral-950 p-4 rounded-md items-end">
                    <div className="flex-1">
                        <label className="block text-xs text-gray-500 mb-1">Guild ID</label>
                        <input 
                            type="text" 
                            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-white text-sm focus:border-blue-600 outline-none"
                            placeholder="e.g. 987654321098765432"
                            value={newGuildState.guild_id}
                            onChange={(e) => setNewGuildState({...newGuildState, guild_id: e.target.value})}
                        />
                    </div>
                    <div className="flex-1">
                        <label className="block text-xs text-gray-500 mb-1">Server Name (Optional)</label>
                        <input 
                            type="text" 
                            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-white text-sm focus:border-blue-600 outline-none"
                            placeholder="e.g. My Community"
                            value={newGuildState.name}
                            onChange={(e) => setNewGuildState({...newGuildState, name: e.target.value})}
                        />
                    </div>
                    <button 
                        onClick={handleAddGuild}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded flex items-center gap-2 h-10 transition-colors"
                    >
                        <Plus size={18} />
                        Add
                    </button>
                </div>

                {/* Guild List */}
                <div className="space-y-2">
                    {(!guilds || guilds.length === 0) && (
                        <div className="text-center text-gray-500 py-4">No allowed guilds found.</div>
                    )}
                    {Array.isArray(guilds) && guilds.map((g, idx) => {
                         if (!g) return null;
                         return (
                        <div key={g.id || idx} className="flex items-center justify-between p-3 bg-neutral-800 rounded border border-neutral-700">
                            <div className="flex items-center gap-3">
                                <div className="h-8 w-8 rounded-full bg-blue-900 flex items-center justify-center text-blue-300 font-bold text-xs">
                                    {g.name && g.name.length > 0 ? g.name[0].toUpperCase() : "S"}
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-white">{g.name || "Unknown Server"}</p>
                                    <p className="text-xs text-gray-500 font-mono">{g.guild_id}</p>
                                </div>
                            </div>
                            <button 
                                onClick={() => g.guild_id && handleRemoveGuild(g.guild_id)}
                                className="text-red-400 hover:text-red-300 hover:bg-red-900/20 p-2 rounded transition-colors"
                                title="Remove Guild"
                            >
                                <Trash2 size={18} />
                            </button>
                        </div>
                    )})}
                </div>
            </div>
            
            {error && <div className="text-red-500 mt-4 text-sm">{error}</div>}

            {/* Invite Modal */}
            {showInviteModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-neutral-900 rounded-lg max-w-lg w-full max-h-[80vh] flex flex-col border border-neutral-800">
                        <div className="p-4 border-b border-neutral-800 flex justify-between items-center">
                            <h3 className="text-lg font-bold text-white">Select Server to Invite</h3>
                            <button onClick={() => setShowInviteModal(false)} className="text-gray-400 hover:text-white">
                                <Plus className="rotate-45" size={24} />
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto flex-1">
                            {userGuilds.length === 0 ? (
                                <p className="text-center text-gray-500 py-8">Loading your servers...</p>
                            ) : (
                                <div className="space-y-2">
                                    {userGuilds.map((guild) => (
                                        <div key={guild.id} className="flex items-center justify-between p-3 bg-neutral-800 rounded hover:bg-neutral-750 transition-colors">
                                           <div className="flex items-center gap-3">
                                                {guild.icon ? (
                                                    <img 
                                                        src={`https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`} 
                                                        alt={guild.name}
                                                        className="w-10 h-10 rounded-full"
                                                    />
                                                ) : (
                                                    <div className="w-10 h-10 rounded-full bg-neutral-700 flex items-center justify-center text-sm font-bold">
                                                        {guild.name.substring(0,2)}
                                                    </div>
                                                )}
                                                <div>
                                                    <p className="font-medium text-white">{guild.name}</p>
                                                    <p className="text-xs text-gray-400">ID: {guild.id}</p>
                                                </div>
                                           </div>
                                           <button 
                                                onClick={() => handleInvite(guild)}
                                                className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm transition-colors"
                                           >
                                               Invite
                                           </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
