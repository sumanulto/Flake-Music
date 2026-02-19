import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Dashboard from './pages/Dashboard';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import GuildMusic from './pages/GuildMusic';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        
        <Route element={<ProtectedRoute />}>
             <Route path="/dashboard" element={<Dashboard />} />
             <Route element={<Layout />}>
                 <Route path="/guild/:guildId" element={<GuildMusic />} />
             </Route>
        </Route>

      </Routes>
    </BrowserRouter>
  );
}

export default App;
