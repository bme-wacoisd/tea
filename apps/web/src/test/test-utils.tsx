import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { GoogleOAuthProvider } from '@react-oauth/google';

const TEST_CLIENT_ID = 'test-client-id';

interface AllProvidersProps {
  children: React.ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  return (
    <GoogleOAuthProvider clientId={TEST_CLIENT_ID}>
      {children}
    </GoogleOAuthProvider>
  );
}

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllProviders, ...options });

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };
