# Deployment to Railway

This app is configured to run on [Railway](https://railway.app), which offers a generous free tier with persistent databases.

## Prerequisites

- GitHub account with your repo pushed
- Railway account (free tier with $5/month credits)
- API keys for LLM providers (Anthropic/Claude or OpenAI)

## Deployment Steps

### 1. Connect GitHub to Railway

1. Go to [railway.app](https://railway.app) and sign up (or sign in with GitHub)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub account
5. Select the repository containing this app

### 2. Add PostgreSQL Database

1. In your Railway project, click "Add Service"
2. Select "Database" > "PostgreSQL"
3. Railway will automatically create the database and inject `DATABASE_URL`

### 3. Configure Environment Variables

In your Railway project settings, add these variables:

```
FLASK_SECRET_KEY=your-long-random-secret-key-here
FLASK_DEBUG=false
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
LLM_PROVIDER=claude
MAX_LINKS_TO_FOLLOW=6
LINK_FETCH_TIMEOUT_SECONDS=8
```

The `DATABASE_URL` is automatically created when you add PostgreSQL.

### 4. Deploy

Railway automatically deploys when you:
- Push to your repository (default branch)
- Manually trigger deploy from the dashboard

Your app will be live at the Railway-generated URL (e.g., `https://your-app.railway.app`).

## File Uploads and Persistent Storage

**Important**: Railway's free tier does not have persistent disk storage between deployments. This means:

- Uploaded CVs and generated documents are stored in `/uploads` and `/generated` directories
- These files will be lost when the app restarts or is redeployed
- For production use, you should configure cloud storage (AWS S3, Google Cloud Storage, etc.)

For now, the app will still work, but users should download their guides immediately after generation.

Railway offers **paid storage volumes** if you need persistent file storage - see their documentation.

## Local Development

The app still works locally with SQLite:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your API keys
python3 app.py
```

Visit `http://127.0.0.1:5001`

## Troubleshooting

- **Database not initializing**: Check Railway logs in the dashboard. The app auto-migrates on first run.
- **Build fails**: Check Railway build logs. Make sure `requirements.txt` has all dependencies.
- **Connection refused**: Verify `DATABASE_URL` environment variable is set in Railway dashboard.
- **Files not persisting**: This is expected on free tier. Files are cleared on redeploy.

## Upgrading from Free Tier

Railway's free tier includes $5/month credits. To keep the app running continuously:

1. **Enable paid plan**: Go to account settings > enable paid features
2. **Persistent storage**: Add a Volume service for `/uploads` and `/generated` directories ($10/month)
3. **Monitor usage**: Railway shows usage in the dashboard

Total for small production: ~$10-20/month depending on usage.

## Railway-Specific Features

- **Automatic HTTPS**: Railway automatically provides SSL certificates
- **Automatic Domain**: Your app gets a `.railway.app` domain
- **Custom Domain**: Upgrade to paid and add your own domain
- **Private Networking**: Services can communicate privately on Railway's network
- **Analytics**: View logs, metrics, and deployments in the dashboard

## Using Your Local Database in Production

If you want to use the SQLite database from your local machine in production:

1. Push your `data/app.db` to the repo (make sure it's not in `.gitignore`)
2. The app will use it instead of PostgreSQL if `DATABASE_URL` is not set

This is **not recommended** for production, as SQLite is single-user and can corrupt over concurrent access.
