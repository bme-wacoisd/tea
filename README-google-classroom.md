# Google Classroom Integration

A web application for integrating with Google Classroom, built with React, TypeScript, Vite, and Turborepo.

## Features

- Google OAuth authentication
- View all your Google Classroom courses
- View students enrolled in each course
- Clean, modern UI with responsive design

## Tech Stack

- **React** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Turborepo** - Monorepo management
- **Google Classroom API** - Course and student data
- **@react-oauth/google** - OAuth integration

## Prerequisites

- Node.js v22+ and npm v10+
- Google Cloud Console account
- Google Classroom courses (to test with)

## Setup Instructions

### 1. Clone and Install

```bash
npm install
```

### 2. Set up Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Classroom API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Classroom API"
   - Click "Enable"

4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Web application"
   - Add authorized JavaScript origins:
     - `http://localhost:3000`
   - Add authorized redirect URIs:
     - `http://localhost:3000`
   - Click "Create"
   - Copy your Client ID

### 3. Configure Environment Variables

1. Navigate to the web app directory:
   ```bash
   cd apps/web
   ```

2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your Google Client ID:
   ```
   VITE_GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
   ```

### 4. Run the Application

From the root directory:

```bash
npm run dev
```

The application will open automatically at `http://localhost:3000`

## Usage

1. Click "Sign in with Google"
2. Grant the requested permissions:
   - View your courses
   - View your course rosters
   - View profile information
3. You'll see a list of your active Google Classroom courses
4. Click on any course to view its enrolled students

## Project Structure

```
google-classroom/
├── apps/
│   └── web/                 # Main React application
│       ├── src/
│       │   ├── components/  # React components
│       │   │   ├── Login.tsx
│       │   │   ├── Dashboard.tsx
│       │   │   ├── ClassList.tsx
│       │   │   └── StudentList.tsx
│       │   ├── App.tsx      # Root component
│       │   ├── main.tsx     # Entry point
│       │   ├── googleApi.ts # Google API utilities
│       │   ├── types.ts     # TypeScript types
│       │   └── index.css    # Styles
│       ├── index.html
│       ├── vite.config.ts
│       └── package.json
├── packages/                # Shared packages (empty for now)
├── turbo.json              # Turborepo configuration
└── package.json            # Root package.json

```

## Available Scripts

From the root directory:

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run type-check` - Run TypeScript type checking
- `npm run lint` - Run ESLint

## API Scopes

The application requests the following Google API scopes:

- `https://www.googleapis.com/auth/classroom.courses.readonly` - View courses
- `https://www.googleapis.com/auth/classroom.rosters.readonly` - View rosters
- `https://www.googleapis.com/auth/classroom.profile.emails` - View email addresses
- `https://www.googleapis.com/auth/classroom.profile.photos` - View profile photos

## Troubleshooting

### "Configuration Error: Please set up your Google Client ID"

Make sure you've created a `.env` file in `apps/web/` with your `VITE_GOOGLE_CLIENT_ID`.

### "Failed to load courses"

1. Verify that the Google Classroom API is enabled in your Google Cloud Console
2. Make sure your OAuth credentials are correctly configured
3. Check that you've granted all requested permissions during login
4. Ensure you have at least one active course in Google Classroom

### OAuth redirect URI mismatch

Make sure `http://localhost:3000` is added to your authorized redirect URIs in the Google Cloud Console.

## Security Notes

- Never commit your `.env` file or expose your Google Client ID publicly
- The `.env` file is already in `.gitignore`
- Only use this application in development with `localhost` origins
- For production deployment, you'll need to add your production domain to the authorized origins

## License

See LICENSE file for details.