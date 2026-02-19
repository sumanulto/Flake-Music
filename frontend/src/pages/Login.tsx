const REDIRECT_URI = import.meta.env.VITE_DISCORD_REDIRECT_URI || 'http://localhost:5173/auth/callback';

export default function Login() {
  const handleLogin = () => {
    // Construct OAuth URL
    const url = `https://discord.com/api/oauth2/authorize?client_id=${import.meta.env.VITE_DISCORD_CLIENT_ID || ''}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&scope=identify%20guilds`;
    window.location.href = url;
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900">
      <div className="bg-gray-800 p-8 rounded-lg shadow-lg text-center">
        <h1 className="text-3xl font-bold mb-6 text-white">Flake Music Login</h1>
        <button
          onClick={handleLogin}
          className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded transition duration-300"
        >
          Login with Discord
        </button>
      </div>
    </div>
  );
}
