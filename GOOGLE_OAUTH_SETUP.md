# Google OAuth Setup Guide

Enable Google Sign-In for your interview app with these steps.

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing one)
3. Enable Google+ API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API"
   - Click "Enable"

## Step 2: Create OAuth Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure OAuth consent screen first:
   - User Type: Internal (or External if you want to share with others)
   - Fill in app name: "Interview Guide Generator"
   - Fill in support email: your email
   - Add scopes: `email`, `profile`, `openid`
   - Add test users (your email)
4. Back to credentials, choose "Web application"
5. Add authorized redirect URIs:
   - `http://127.0.0.1:5001/auth/google/callback` (local development)
   - `https://your-railway-app.railway.app/auth/google/callback` (production)
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

## Step 3: Add to Environment

### Local Development (.env)

```bash
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://127.0.0.1:5001/auth/google/callback
```

### Railway Production

1. Go to your Railway project dashboard
2. Click your web service
3. Go to "Variables"
4. Add:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=https://your-app.railway.app/auth/google/callback
   ```

## Step 4: Test Locally

```bash
source venv/bin/activate
pip install -r requirements.txt  # Updated with authlib
python3 app.py
```

Visit http://127.0.0.1:5001/login and you should see "Sign in with Google" button.

## How It Works

1. User clicks "Sign in with Google"
2. Redirected to Google login
3. Google verifies credentials
4. Redirected back to your app with user info
5. App auto-creates user if doesn't exist
6. User is logged in

## Important Notes

- **Auto-creates users**: If email is verified by Google but doesn't exist locally, the app creates a new user with `role: "user"`
- **Email-based**: Uses Google email as unique identifier
- **Password**: A dummy password is set (won't be used since Google handles auth)
- **Optional**: If GOOGLE_CLIENT_ID is not set, the Google button won't show

## Troubleshooting

### "redirect_uri_mismatch" Error
- Make sure redirect URI in Google Console matches exactly
- Local: `http://127.0.0.1:5001/auth/google/callback`
- Production: `https://your-railway-app.railway.app/auth/google/callback`

### Google Button Not Showing
- Check GOOGLE_CLIENT_ID is in .env
- Restart the app: `python3 app.py`
- Check browser console for any errors

### User Can't Log In
- Verify Google+ API is enabled in Google Cloud
- Check email is in test users list (for testing)
- Try regular email/password login as fallback

## Security Notes

- **Client Secret**: Never commit to git (it's in `.gitignore`)
- **Tokens**: Stored securely in Flask session
- **HTTPS**: Required in production (Railway provides HTTPS)
- **Scope**: Only requests `email` and `profile`

## References

- [Authlib Flask Integration](https://docs.authlib.org/en/latest/client/frameworks.html#flask-client)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
