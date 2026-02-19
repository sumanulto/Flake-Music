import { useEffect, useRef } from 'react';
import { usePlayerStore } from '../store/usePlayerStore';

export function useWebSocket(guildId: string | undefined) {
  const ws = useRef<WebSocket | null>(null);
  const setPlayerState = usePlayerStore((state) => state.setPlayerState);

  useEffect(() => {
    if (!guildId) return;

    const connect = () => {
       // In production, use wss if https
       const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
       ws.current = new WebSocket(`${protocol}://localhost:8000/ws/${guildId}`);

       ws.current.onopen = () => {
         console.log('WS Connected');
       };

       ws.current.onmessage = (event) => {
         const data = JSON.parse(event.data);
         console.log('WS Message:', data);
         
         if (data.event === 'TRACK_START') {
            setPlayerState({
                isPlaying: true,
                currentTrack: {
                    title: data.track,
                    author: data.author,
                    duration: data.duration,
                    position: 0
                }
            });
         } else if (data.event === 'TRACK_END') {
             setPlayerState({ isPlaying: false, currentTrack: null });
         } else if (data.event === 'PLAYER_UPDATE') {
             // Handle periodic updates if backend sends them
         }
       };

       ws.current.onclose = () => {
         console.log('WS Disconnected, retrying...');
         setTimeout(connect, 3000);
       };
    };

    connect();

    return () => {
      ws.current?.close();
    };
  }, [guildId, setPlayerState]);

  return ws.current;
}
