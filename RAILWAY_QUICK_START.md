# Railway Quick Start

Your app is now configured for [Railway](https://railway.app) deployment. Here's the fastest path to get it live:

## In 5 Minutes

### 1. Create Railway Account
- Go to https://railway.app
- Sign up with GitHub (recommended)
- Authorize Railway to access your account

### 2. Create New Project
- Click "New Project"
- Select "Deploy from GitHub repo"
- Choose your interview-app repository
- Railway will auto-detect Python and start building

### 3. Add PostgreSQL Database
- Once deployed, go to your project
- Click "Add Service"
- Select "Database" > "PostgreSQL"
- Railway creates it and auto-injects `DATABASE_URL`

### 4. Set Environment Variables
- In your Railway project, go to "Variables"
- Add these:
  ```
  FLASK_SECRET_KEY=change-me-to-something-random
  FLASK_DEBUG=false
  LLM_PROVIDER=claude
  ANTHROPIC_API_KEY=sk-ant-...
  OPENAI_API_KEY=sk-proj-... (optional)
  MAX_LINKS_TO_FOLLOW=6
  LINK_FETCH_TIMEOUT_SECONDS=8
  ```

### 5. Deploy
- Railway auto-deploys when you push to GitHub
- Your app is live at `https://your-app.railway.app`
- Click the domain in Railway dashboard to visit it

## Deployment Files

- **Procfile** - Tells Railway how to start the app (`gunicorn app:app`)
- **railway.json** - Optional Railway configuration
- **requirements.txt** - Python dependencies (includes `gunicorn` and `psycopg2-binary`)
- **interview_app/__init__.py** - App factory with database auto-detection

## What's Different from Local

| Local | Railway |
|-------|---------|
| SQLite (data/app.db) | PostgreSQL (Railway managed) |
| Flask dev server | Gunicorn WSGI server |
| http://127.0.0.1:5001 | https://your-app.railway.app |
| DATABASE_URL not set | DATABASE_URL auto-injected |

## First Deploy Checklist

- [ ] Create Railway account
- [ ] Connect GitHub repo
- [ ] Create PostgreSQL database
- [ ] Set environment variables
- [ ] Verify app deploys (check "Deployments" tab)
- [ ] Visit your Railway URL
- [ ] Test login (should show login form)

## After Deploy

**Migrate your data** (if you have existing local data):
```bash
python3 migrate_to_postgres.py "postgresql://user:pass@railway-host:5432/railway"
```

See [MIGRATE_DB.md](MIGRATE_DB.md) for full migration steps.

## Useful Railway Links

- **Dashboard**: https://railway.app/dashboard
- **Docs**: https://railway.app/docs
- **Status**: https://railway-status.up.railway.app
- **Pricing**: https://railway.app/pricing (free tier: $5/month credits)

## Troubleshooting

### Build Failed
- Check "Build" tab in Railway dashboard
- Common issue: Missing environment variable
- Solution: Add all required vars listed above

### App Crashes
- View "Logs" tab in Railway dashboard
- Check for `DATABASE_URL` errors
- Verify PostgreSQL service is running

### Database Connection Refused
- Confirm PostgreSQL service exists in project
- Check `DATABASE_URL` is in environment variables
- Redeploy after adding the database

## Local Development Still Works

Your local setup is unchanged:
```bash
source venv/bin/activate
python3 app.py
# Visit http://127.0.0.1:5001
```

The app automatically detects:
- **No DATABASE_URL** → uses local SQLite
- **DATABASE_URL set** → uses PostgreSQL (works locally too)

## Common Next Steps

1. **Set up custom domain**: In Railway settings (paid tier)
2. **Add file storage**: Railway Volumes service ($10/month)
3. **Set up monitoring**: Railway includes logs, metrics, etc.
4. **Keep app warm**: Railway's uptime settings prevent auto-sleep
5. **Backup database**: Regular PostgreSQL backups (paid feature)

## Getting Help

- Railway Docs: https://railway.app/docs
- Railway Discord: https://discord.gg/railway
- Check DEPLOY.md for more detailed deployment info
