import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { AxiosResponse } from 'axios';
import { api } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { usePlayerStore } from '../store/usePlayerStore';
import { Play, Pause, SkipForward, Volume2, Search } from 'lucide-react';
import { formatTime } from '../lib/utils';

interface GuildMusicStateResponse {
  is_playing: boolean;
  volume: number;
  queue: string[];
  title?: string;
  author?: string;
  duration?: number;
  position?: number;
}

export default function GuildMusic() {
  const { guildId } = useParams();
  useWebSocket(guildId);
  
  const { isPlaying, currentTrack, queue, volume, setPlayerState } = usePlayerStore();
  const [query, setQuery] = useState('');

  // Initial fetch
  useEffect(() => {
    if (guildId) {
        api.get(`/music/${guildId}`)
         .then((res: AxiosResponse<GuildMusicStateResponse>) => {
               const data = res.data;
               setPlayerState({
                   isPlaying: data.is_playing,
                   volume: data.volume,
                   queue: data.queue,
                   currentTrack: data.title ? {
                       title: data.title,
                       author: data.author ?? 'Unknown',
                       duration: data.duration ?? 0,
                       position: data.position ?? 0
                   } : null
               });
           })
           .catch(console.error);
    }
  }, [guildId, setPlayerState]);

  // Progress tick
  useEffect(() => {
    let interval: number;
    if (isPlaying) {
        interval = window.setInterval(() => {
            usePlayerStore.getState().updatePosition(1000);
        }, 1000);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  const handlePlay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || !guildId) return;
    try {
        await api.post('/music/play', { guild_id: guildId, query });
        setQuery('');
    } catch (err) {
        console.error(err);
    }
  };

  const togglePause = async () => {
      if (!guildId) return;
      await api.post(`/music/${guildId}/pause`);
      setPlayerState({ isPlaying: !isPlaying });
  };

  const skip = async () => {
      if (!guildId) return;
      await api.post(`/music/${guildId}/skip`);
  };

  const changeVolume = async (vol: number) => {
      if (!guildId) return;
      setPlayerState({ volume: vol }); // Optimistic
      await api.post(`/music/${guildId}/volume`, { volume: vol });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Search */}
      <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
        <form onSubmit={handlePlay} className="flex gap-4">
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for a song or paste a URL..."
            className="flex-1 bg-gray-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button type="submit" className="bg-indigo-600 hover:bg-indigo-700 p-3 rounded-lg text-white">
            <Search size={24} />
          </button>
        </form>
      </div>

      {/* Now Playing */}
      <div className="bg-gradient-to-br from-indigo-900 to-gray-900 p-8 rounded-xl shadow-2xl border border-gray-700">
        <div className="flex flex-col md:flex-row items-center gap-8">
           {/* Album Art Placeholder */}
           <div className="w-48 h-48 bg-gray-800 rounded-lg shadow-lg flex items-center justify-center">
             <span className="text-4xl">🎵</span>
           </div>

           <div className="flex-1 w-full text-center md:text-left">
             <h2 className="text-3xl font-bold text-white mb-2">{currentTrack?.title || "Nothing Playing"}</h2>
             <p className="text-gray-400 text-lg mb-6">{currentTrack?.author || "Start adding songs to the queue"}</p>

             {/* Progress Bar */}
             <div className="w-full mb-6">
                <input 
                    type="range" 
                    min="0" 
                    max={currentTrack?.duration || 0} 
                    value={currentTrack?.position || 0}
                    onChange={(e) => {
                        const newPos = parseInt(e.target.value);
                        setPlayerState({ 
                            currentTrack: currentTrack ? { ...currentTrack, position: newPos } : null 
                        });
                    }}
                    onMouseUp={async (e) => {
                         const target = e.target as HTMLInputElement;
                         const newPos = parseInt(target.value);
                         if (!guildId) return;
                         await api.put(`/music/${guildId}/seek`, { position: newPos });
                    }}
                    className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>{currentTrack ? formatTime(currentTrack.position) : "0:00"}</span>
                    <span>{currentTrack ? formatTime(currentTrack.duration) : "0:00"}</span>
                </div>
             </div>

             {/* Controls */}
             <div className="flex items-center justify-center md:justify-start gap-6">
                <button onClick={togglePause} className="p-4 bg-white text-black rounded-full hover:scale-105 transition">
                    {isPlaying ? <Pause size={24} fill="black" /> : <Play size={24} fill="black" />}
                </button>
                <button onClick={skip} className="p-3 text-white hover:text-indigo-400 transition">
                    <SkipForward size={32} />
                </button>
                
                {/* Volume */}
                <div className="flex items-center gap-2 ml-auto">
                    <Volume2 size={20} className="text-gray-400" />
                    <input 
                        type="range" 
                        min="0" 
                        max="100" 
                        value={volume} 
                        onChange={(e) => changeVolume(parseInt(e.target.value))}
                        className="w-24 accent-indigo-500"
                    />
                </div>
             </div>
           </div>
        </div>
      </div>

      {/* Queue */}
      <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
        <h3 className="text-xl font-bold mb-4">Up Next</h3>
        {queue.length === 0 ? (
            <p className="text-gray-400">Queue is empty.</p>
        ) : (
            <ul className="space-y-3">
                {queue.map((track, i) => (
                    <li key={i} className="flex items-center gap-4 p-3 bg-gray-700/50 rounded-lg">
                        <span className="text-gray-400 font-mono">{i + 1}</span>
                        <span>{track}</span>
                    </li>
                ))}
            </ul>
        )}
      </div>
    </div>
  );
}
