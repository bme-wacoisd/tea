import { useGoogleLogin } from '@react-oauth/google';
import { GoogleUser } from '../types';
import { SCOPES } from '../googleApi';

interface LoginProps {
  onLoginSuccess: (token: string, user: GoogleUser) => void;
}

function Login({ onLoginSuccess }: LoginProps) {
  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        // Fetch user info
        const userInfoResponse = await fetch(
          'https://www.googleapis.com/oauth2/v3/userinfo',
          {
            headers: {
              Authorization: `Bearer ${tokenResponse.access_token}`,
            },
          }
        );

        const userInfo = await userInfoResponse.json();

        const googleUser: GoogleUser = {
          email: userInfo.email,
          name: userInfo.name,
          picture: userInfo.picture,
        };

        onLoginSuccess(tokenResponse.access_token, googleUser);
      } catch (error) {
        console.error('Error fetching user info:', error);
      }
    },
    onError: (error) => {
      console.error('Login failed:', error);
    },
    scope: SCOPES,
  });

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>Welcome to Google Classroom Integration</h2>
        <p>
          Connect your Google account to access your Google Classroom courses
          and manage your students.
        </p>
        <button onClick={() => login()} className="button button-primary">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}

export default Login;
