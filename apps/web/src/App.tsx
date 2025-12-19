import { useState, useEffect } from 'react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import { GoogleUser } from './types';
import { initializeGapi, setAccessToken } from './googleApi';

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

function App() {
  const [user, setUser] = useState<GoogleUser | null>(null);
  const [_accessToken, setAccessTokenState] = useState<string | null>(null);
  const [gapiReady, setGapiReady] = useState(false);

  useEffect(() => {
    initializeGapi()
      .then(() => {
        setGapiReady(true);
      })
      .catch((error) => {
        console.error('Failed to initialize GAPI:', error);
      });
  }, []);

  const handleLoginSuccess = (token: string, userInfo: GoogleUser) => {
    setAccessTokenState(token);
    setUser(userInfo);
    setAccessToken(token);
  };

  const handleLogout = () => {
    setUser(null);
    setAccessTokenState(null);
  };

  if (!CLIENT_ID) {
    return (
      <div className="app">
        <div className="header">
          <h1>Google Classroom Integration</h1>
        </div>
        <div className="container">
          <div className="error">
            <strong>Configuration Error:</strong> Please set up your Google Client ID in the .env file.
            <br />
            <br />
            Copy .env.example to .env and add your Google OAuth Client ID.
          </div>
        </div>
      </div>
    );
  }

  if (!gapiReady) {
    return (
      <div className="app">
        <div className="header">
          <h1>Google Classroom Integration</h1>
        </div>
        <div className="container">
          <div className="loading">Initializing...</div>
        </div>
      </div>
    );
  }

  return (
    <GoogleOAuthProvider clientId={CLIENT_ID}>
      <div className="app">
        <div className="header">
          <h1>Google Classroom Integration</h1>
        </div>
        {!user ? (
          <Login onLoginSuccess={handleLoginSuccess} />
        ) : (
          <Dashboard user={user} onLogout={handleLogout} />
        )}
      </div>
    </GoogleOAuthProvider>
  );
}

export default App;
