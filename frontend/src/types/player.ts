export interface PlayerCurrent {
  title: string;
  author?: string;
  duration?: number;
  uri?: string;
  thumbnail?: string;
}

export interface PlayerQueueItem {
  title: string;
  author?: string;
  duration?: number;
  thumbnail?: string;
}

export interface PlayerSettings {
    shuffleEnabled: boolean;
    repeatMode: 'off' | 'one' | 'all';
    volume: number;
}

export interface Player {
  guildId: string;
  guildName?: string;
  voiceChannel: string;
  textChannel: string;
  connected: boolean;
  playing: boolean;
  paused: boolean;
  position: number;
  volume: number;
  current?: PlayerCurrent | null;
  queue: PlayerQueueItem[];
  settings?: PlayerSettings;
}
