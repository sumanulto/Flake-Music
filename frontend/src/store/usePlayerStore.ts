import { create } from 'zustand';

interface PlayerState {
  isPlaying: boolean;
  currentTrack: {
    title: string;
    author: string;
    duration: number;
    position: number;
  } | null;
  queue: string[];
  volume: number;
  setPlayerState: (state: Partial<PlayerState>) => void;
  updatePosition: (ms: number) => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  isPlaying: false,
  currentTrack: null,
  queue: [],
  volume: 100,
  setPlayerState: (state) => set((prev) => ({ ...prev, ...state })),
  updatePosition: (ms) => set((prev) => {
    if (!prev.currentTrack) return prev;
    return {
      ...prev,
      currentTrack: {
        ...prev.currentTrack,
        position: prev.currentTrack.position + ms
      }
    };
  })
}));
