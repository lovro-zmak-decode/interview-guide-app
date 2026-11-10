# Deployment notes

What the app needs to run somewhere other than a laptop. There is no deployment automation yet
(ADR 0015); this page records what a deployment must provide, so it can be set up by hand or
automated later. The first target is Railway.

## Required settings

| Variable | Notes |
|---|---|
| `FLASK_SECRET_KEY` | Long random string. The app refuses to start without it. Never reuse the local one |
| `DATABASE_URL` | The PostgreSQL URL. `postgres://` and `postgresql://` are both accepted |
| `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` | At least one, for generating guides and summaries |

## Optional settings

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Default provider in the form |
| `OPENAI_MODEL` | `gpt-4o` | Any OpenAI chat model that supports JSON output |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | |
| `FILE_STORAGE` | `database` | Where uploaded CV and LinkedIn files are kept (ADR 0006) |
| `MAX_LINKS_TO_FOLLOW`, `LINK_FETCH_TIMEOUT_SECONDS` | 6, 8 | Links followed from the CV |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | unset | Google sign-in; the redirect is `https://<domain>/auth/google/callback` and must also be registered in Google Cloud Console |

## How it runs

- **Start command** (also in `railway.json` and `Procfile`):
  `gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers 2 --threads 4 --timeout 180`.
  Guide generation takes up to a minute, so the default 30 second worker timeout is too short.
- **Health check:** `GET /healthz` returns `ok` without a login, and 503 when the database cannot
  be reached. Do not use `/`: it redirects to the setup or login page.
- **Python:** `.python-version` pins 3.13 for the build.
- **Tables** are created automatically at start-up. Existing databases get the few added columns
  the same way. There are no separate migration steps.
- **Nothing is written to disk that must survive a deploy** (ADR 0006, ADR 0007).

## First deployment checklist

1. Connect the GitHub repository (branch `main`) and add a PostgreSQL service in the same project.
2. Set the required variables. `DATABASE_URL` should reference the PostgreSQL service.
3. Generate a public domain.
4. **Open the app and create your account on `/setup` straight away.** Whoever reaches that page
   first becomes the superadmin. Do it before sharing the link.
5. Create the system prompts (types `technical` and `summary`), and copy over the question bank and
   interview roles if you have them elsewhere. A prompt is data, not code.
6. Generate a test guide, start an interview, end it and write the summary.
7. Invite the team from Admin, Users.

## Not automated

Building, releasing, rolling back and preview environments. Railway can redeploy when `main`
changes if the repository is connected, but that is a hosting setting. Record any pipeline as its
own decision in `docs/adr/` when it is defined.
