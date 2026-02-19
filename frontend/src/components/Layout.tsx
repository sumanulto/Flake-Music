import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { LogOut, Server } from 'lucide-react';

export default function Layout() {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 flex flex-col border-r border-gray-700">
        <div className="p-6 text-2xl font-bold bg-indigo-600">Flake Music</div>
        
        <nav className="flex-1 p-4 space-y-2">
          <NavLink 
            to="/dashboard"
            className={({ isActive }) => `flex items-center gap-3 px-4 py-3 rounded-md transition ${isActive ? 'bg-indigo-600 text-white' : 'hover:bg-gray-700 text-gray-300'}`}
          >
            <Server size={20} />
            Guilds
          </NavLink>
        </nav>

        <div className="p-4 border-t border-gray-700">
          <button 
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-4 py-3 rounded-md hover:bg-red-600 transition text-gray-300 hover:text-white"
          >
            <LogOut size={20} />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-gray-950 p-8">
        <Outlet />
      </main>
    </div>
  );
}
