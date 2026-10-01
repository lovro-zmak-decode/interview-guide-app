# Testing Google OAuth Locally

Quick guide to test the Google OAuth login flow locally.

## Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable Google+ API:
   - APIs & Services > Library
   - Search "Google+ API" 
   - Click "Enable"

### 2. Create OAuth Credentials

1. APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - Choose "Internal" or "External"
   - Fill in app name: "Interview Guide App"
   - Add your email as test user
4. Choose "Web application"
5. Add authorized redirect URI:
   - `http://127.0.0.1:5001/auth/google/callback`
6. Click "Create"
7. Copy **Client ID** and **Client Secret**

### 3. Configure .env

Add to your `.env` file:

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:5001/auth/google/callback
```

### 4. Install Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt  # Updates with authlib
```

### 5. Restart the App

```bash
pkill -f "python.*app.py"
python3 app.py
```

## Testing

### Login with Google

1. Visit http://127.0.0.1:5001/login
2. You should see "Sign in with Google" button
3. Click it
4. You'll be redirected to Google login
5. Sign in with your test account (the one you added to OAuth consent screen)
6. You'll be redirected back and auto-logged in

### What Happens

1. **First time login**: 
   - User is created automatically with `role: "user"`
   - Dummy password is set (OAuth doesn't use passwords)
   - User is logged in and redirected to dashboard

2. **Subsequent logins**:
   - Existing user is found and logged in
   - No new user is created

### Logs

Check app logs for:

```
Google OAuth configured successfully
User logged in via Google OAuth: your-email@example.com
Auto-created user from Google OAuth: your-email@example.com
```

## Troubleshooting

### "Google OAuth is not configured" Message

- Check `.env` has `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- Restart the app after changes
- Check app logs for "Google OAuth configured"

### "redirect_uri_mismatch" Error

- Verify redirect URI in Google Console matches exactly:
  - Local: `http://127.0.0.1:5001/auth/google/callback`
  - Production: `https://your-app.railway.app/auth/google/callback`

### User Not Created

- Check database logs
- Verify email from Google account
- Check app logs for creation errors

### Session Not Starting

- Clear browser cookies for localhost
- Try in incognito/private mode
- Check Flask secret key in .env

## Next Steps

- Deploy to Railway with production Google OAuth credentials
- Add admin role assignment for specific emails
- Consider email verification for auto-created accounts
- Add logout confirmation page

## References

- [Authlib Flask OAuth Docs](https://docs.authlib.org/en/latest/client/frameworks.html#flask-client)
- [Google OAuth Docs](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
