import { useEffect, useState } from 'react';
import logoUrl from '/tab.png';

const REDIRECT_URI = import.meta.env.VITE_DISCORD_REDIRECT_URI || 'http://localhost:5173/auth/callback';

const commands = [
  {
    name: '/play',
    description: 'Play a song or playlist from YouTube, Spotify, or any URL.',
    example: '/play Never Gonna Give You Up',
  },
  {
    name: '/skip',
    description: 'Skip the currently playing track and move to the next one.',
    example: '/skip',
  },
  {
    name: '/queue',
    description: 'View the current song queue for your server.',
    example: '/queue',
  },
  {
    name: '/pause',
    description: 'Pause or resume the current track.',
    example: '/pause',
  },
  {
    name: '/volume',
    description: 'Set the playback volume (0–100).',
    example: '/volume 75',
  },
  {
    name: '/filter',
    description: 'Apply audio filters like bassboost, nightcore, vaporwave & more.',
    example: '/filter bassboost',
  },
  {
    name: '/playlist',
    description: 'Manage your saved playlists — create, add, play, or delete.',
    example: '/playlist create MyMix',
  },
  {
    name: '/nowplaying',
    description: 'Display information about the currently playing track.',
    example: '/nowplaying',
  },
];

const features = [
  { icon: '🎵', title: 'Crystal Clear Audio', desc: 'Powered by Lavalink for high-quality, lag-free music playback.' },
  { icon: '📋', title: 'Smart Playlists', desc: 'Save and manage your favourite tracks across sessions.' },
  { icon: '🎛️', title: 'Audio Filters', desc: 'Bassboost, Nightcore, Vaporwave and more — in one command.' },
  { icon: '🌐', title: 'Web Dashboard', desc: 'Control the bot directly from your browser with a real-time UI.' },
  { icon: '🔀', title: 'Shuffle & Repeat', desc: 'Queue management with shuffle, repeat-one and repeat-all modes.' },
  { icon: '🔒', title: 'Admin Controls', desc: 'Settings and guild management are restricted to authorised admins.' },
  { icon: '🤖', title: 'AI Voice Commands', desc: 'Speak naturally — AI understands your voice commands to play, skip, search & more hands-free.' },
];

export default function Login() {
  const [year, setYear] = useState(new Date().getFullYear());

  useEffect(() => {
    const interval = setInterval(() => {
      setYear(new Date().getFullYear());
    }, 1000 * 60 * 60); // refresh every hour
    return () => clearInterval(interval);
  }, []);

  const handleLogin = () => {
    const url = `https://discord.com/api/oauth2/authorize?client_id=${import.meta.env.VITE_DISCORD_CLIENT_ID || ''}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&scope=identify%20guilds`;
    window.location.href = url;
  };

  return (
    <div className="min-h-screen bg-[#080a08] text-white flex flex-col">

      {/* ── Hero ── */}
      <section className="relative flex flex-col items-center justify-center text-center px-6 py-24 overflow-hidden">
        {/* Background ambient video */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          style={{ opacity: 0.12 }}
        >
          <source src="/beach water.mp4" type="video/mp4" />
        </video>

        {/* Animated glowing background orbs */}
        <style>{`
          @keyframes orbPulse {
            0%, 100% { opacity: 0.18; transform: translateX(-50%) scale(1); }
            50%        { opacity: 0.32; transform: translateX(-50%) scale(1.12); }
          }
          @keyframes orbDrift {
            0%, 100% { opacity: 0.08; transform: scale(1) translateY(0px); }
            50%        { opacity: 0.18; transform: scale(1.1) translateY(-20px); }
          }
          @keyframes logoGlow {
            0%, 100% { box-shadow: 0 0 32px 8px rgba(34,197,94,0.35); }
            50%        { box-shadow: 0 0 56px 16px rgba(52,211,153,0.55); }
          }
        `}</style>
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div style={{
            position: 'absolute',
            top: '-120px',
            left: '50%',
            width: '600px',
            height: '600px',
            borderRadius: '9999px',
            background: 'radial-gradient(circle, rgba(34,197,94,0.22) 0%, transparent 70%)',
            filter: 'blur(80px)',
            animation: 'orbPulse 6s ease-in-out infinite',
          }} />
          <div style={{
            position: 'absolute',
            bottom: '-80px',
            right: '25%',
            width: '420px',
            height: '420px',
            borderRadius: '9999px',
            background: 'radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 70%)',
            filter: 'blur(90px)',
            animation: 'orbDrift 8s ease-in-out infinite',
          }} />
          <div style={{
            position: 'absolute',
            top: '30%',
            left: '10%',
            width: '300px',
            height: '300px',
            borderRadius: '9999px',
            background: 'radial-gradient(circle, rgba(5,150,105,0.12) 0%, transparent 70%)',
            filter: 'blur(70px)',
            animation: 'orbDrift 10s ease-in-out infinite reverse',
          }} />
        </div>

        {/* Logo — circular with animated glow ring */}
        <div
          className="relative mb-6 flex items-center justify-center w-28 h-28 rounded-full border-2 border-green-500/50 bg-black/40 overflow-hidden"
          style={{ animation: 'logoGlow 4s ease-in-out infinite' }}
        >
          <img
            src={logoUrl}
            alt="Flake Music Logo"
            className="w-full h-full object-cover rounded-full"
          />
        </div>

        <h1 className="relative text-5xl md:text-6xl font-extrabold tracking-tight mb-4 bg-gradient-to-r from-green-300 via-emerald-400 to-teal-300 bg-clip-text text-transparent drop-shadow-lg">
          Flake Music
        </h1>
        <p className="relative max-w-xl text-lg text-green-200/70 mb-8">
          A powerful Discord music bot with a real-time web dashboard. Stream from YouTube, Spotify, and more — all from your browser or Discord.
        </p>

        <button
          id="login-with-discord"
          onClick={handleLogin}
          className="relative group flex items-center gap-3 bg-[#5865F2] hover:bg-[#4752c4] active:scale-95 text-white font-bold py-3.5 px-8 rounded-xl transition-all duration-200 shadow-[0_4px_24px_rgba(88,101,242,0.5)] hover:shadow-[0_4px_32px_rgba(88,101,242,0.7)] text-lg"
        >
          {/* Discord logo SVG */}
          <svg className="w-6 h-6 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057c.002.022.015.043.033.053a19.897 19.897 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
          </svg>
          Login with Discord
        </button>

        <p className="relative mt-4 text-sm text-green-200/40">
          Access is granted only to users approved by an admin.
        </p>
      </section>

      {/* ── Features ── */}
      <section className="px-6 py-16 max-w-6xl mx-auto w-full">
        <h2 className="text-center text-3xl font-bold text-green-300 mb-10">What Flake Music Can Do</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f) => (
            <div
              key={f.title}
              className="group relative rounded-2xl border border-green-900/50 bg-green-950/20 hover:bg-green-900/30 p-6 transition-all duration-300 hover:border-green-600/60 hover:shadow-[0_0_24px_rgba(34,197,94,0.12)] cursor-default"
            >
              <div className="text-4xl mb-3">{f.icon}</div>
              <h3 className="text-lg font-semibold text-green-200 mb-1">{f.title}</h3>
              <p className="text-sm text-green-200/55 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Commands ── */}
      <section className="px-6 py-16 bg-green-950/10 border-y border-green-900/30">
        <div className="max-w-6xl mx-auto w-full">
          <h2 className="text-center text-3xl font-bold text-green-300 mb-3">Slash Commands</h2>
          <p className="text-center text-sm text-green-200/50 mb-10">Use these directly in any Discord server where Flake Music is active.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {commands.map((cmd) => (
              <div
                key={cmd.name}
                className="group flex flex-col gap-1.5 rounded-xl border border-green-900/50 bg-[#0b0f0b] hover:border-green-600/50 hover:bg-green-950/30 p-5 transition-all duration-200"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-base font-bold text-green-400 group-hover:text-green-300 transition-colors">{cmd.name}</span>
                </div>
                <p className="text-sm text-green-200/60 leading-relaxed">{cmd.description}</p>
                <div className="mt-1 rounded-lg bg-black/40 border border-green-900/30 px-3 py-1.5 font-mono text-xs text-green-500/80">
                  {cmd.example}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Admin Note ── */}
      <section className="px-6 py-14 max-w-3xl mx-auto w-full text-center">
        <div className="rounded-2xl border border-amber-700/40 bg-amber-950/20 p-8 shadow-[0_0_40px_rgba(217,119,6,0.08)]">
          <div className="text-4xl mb-3">🔒</div>
          <h3 className="text-xl font-bold text-amber-300 mb-2">Admin-Only Settings</h3>
          <p className="text-sm text-amber-200/60 leading-relaxed">
            Bot configuration, guild whitelisting, invite management, and advanced settings are accessible{' '}
            <span className="text-amber-300 font-semibold">only to authorised admins</span>. If you need access,
            contact your server administrator. Admins can grant or revoke permissions at any time from the dashboard.
          </p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="mt-auto border-t border-green-900/30 py-6 text-center text-sm text-green-200/35 px-4">
        <p className="mb-1">
          © {year} Flake Music. All rights reserved.
        </p>
        <p>
          Powered by{' '}
          <a
            href="https://discord.gg/dMHj344eb4"
            target="_blank"
            rel="noopener noreferrer"
            className="text-green-400/70 hover:text-green-300 underline underline-offset-2 transition-colors"
          >
            Kraftamine
          </a>
          {' '}· Made with{' '}
          <span className="text-red-400">♥</span>
          {' '}by{' '}
          <a
            href="https://suman.kraftamine.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-green-400/70 hover:text-green-300 underline underline-offset-2 transition-colors"
          >
            sumanulto
          </a>
        </p>
      </footer>
    </div>
  );
}
