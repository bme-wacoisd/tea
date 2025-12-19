import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Login from './Login';

// Mock the @react-oauth/google hook
vi.mock('@react-oauth/google', async () => {
  const actual = await vi.importActual('@react-oauth/google');
  return {
    ...actual,
    useGoogleLogin: () => vi.fn(),
  };
});

const renderWithProvider = (component: React.ReactElement) => {
  return render(
    <GoogleOAuthProvider clientId="test-client-id">
      {component}
    </GoogleOAuthProvider>
  );
};

describe('Login Component', () => {
  it('renders the welcome message', () => {
    const mockOnLoginSuccess = vi.fn();
    renderWithProvider(<Login onLoginSuccess={mockOnLoginSuccess} />);

    expect(
      screen.getByText('Welcome to Google Classroom Integration')
    ).toBeInTheDocument();
  });

  it('renders the description text', () => {
    const mockOnLoginSuccess = vi.fn();
    renderWithProvider(<Login onLoginSuccess={mockOnLoginSuccess} />);

    expect(
      screen.getByText(/Connect your Google account/i)
    ).toBeInTheDocument();
  });

  it('renders the sign in button', () => {
    const mockOnLoginSuccess = vi.fn();
    renderWithProvider(<Login onLoginSuccess={mockOnLoginSuccess} />);

    expect(
      screen.getByRole('button', { name: /sign in with google/i })
    ).toBeInTheDocument();
  });

  it('has the correct CSS classes', () => {
    const mockOnLoginSuccess = vi.fn();
    const { container } = renderWithProvider(
      <Login onLoginSuccess={mockOnLoginSuccess} />
    );

    expect(container.querySelector('.login-container')).toBeInTheDocument();
    expect(container.querySelector('.login-card')).toBeInTheDocument();
  });
});
