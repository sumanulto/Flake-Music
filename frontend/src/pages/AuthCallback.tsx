import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuthStore } from '../store/useAuthStore';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const setUser = useAuthStore((state) => state.setUser);
  const called = useRef(false);

  useEffect(() => {
    const code = searchParams.get('code');
    if (code && !called.current) {
      called.current = true;
      api.post(`/auth/callback?code=${code}`)
        .then((res) => {
          setAccessToken(res.data.access_token);
          setAccessToken(res.data.access_token);
          // Fetch user info
          api.get('/auth/me').then(userRes => {
              // Convert ID to number if needed or ensure store handles string?
              // Store expects number for ID based on previous view.
              // We should probably update store to accept string or cast here if safe (JS precision issue if truly huge?)
              // Discord IDs are > 2^53 sometimes. Strings are safer.
              // Let's try to parse, but be aware. 
              // Actually, best to update Store to use string ID.
              const userData = userRes.data;
              setUser({
                  ...userData,
                  id: userData.id // Keep as string
              });
              navigate('/dashboard');
          });
        })
        .catch((err) => {
          console.error("Login failed", err);
          navigate('/');
        });
    } else if (!code) {
      navigate('/');
    }
  }, [searchParams, navigate, setAccessToken]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
      Processing login...
    </div>
  );
}
