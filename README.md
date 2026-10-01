# Interview Summary Generator

Local Python/Flask app that takes a candidate's CV and LinkedIn info, researches
linked projects (GitHub, portfolio sites, etc.), and calls an LLM (Claude or
OpenAI, your choice) to generate a first-interview guide as a `.docx`, in English.

## Quick install & run

```bash
cd interview-summary-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill out the `.env` file with the right values (see [Setup](#setup) below), then:

```bash
python3 app.py
```

If `python3 app.py` fails with `ModuleNotFoundError: No module named 'dotenv'` (or any other
package), your virtual environment isn't activated in this terminal session — every new
terminal window/tab needs this run again before `python3 app.py` will work:

```bash
cd interview-summary-app
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

If `.venv` doesn't exist at all yet in this folder, create it first with `python3 -m venv .venv`,
then activate it and install as above.

## How it works

- You log in (see [Accounts and roles](#accounts-and-roles) below).
- You upload a CV (PDF/DOCX/TXT) and provide LinkedIn info (paste text, or upload a LinkedIn
  "Save to PDF" export), plus a candidate name, interview role, duration, LLM provider, and which
  system prompt to use.
- Optionally, you tick off specific questions (or whole groups) from your Own Questions DB or the
  shared Questions DB to feed into the guide.
- The app extracts text from the CV/LinkedIn, finds URLs mentioned in them (GitHub repos, personal
  sites, project demos), and fetches those pages one level deep, best-effort — broken links are
  skipped, not fatal.
- All of that is bundled into a prompt (read from the database — see
  [System Prompts](#system-prompts)) sent to your chosen LLM, asking for a structured JSON
  interview guide: profile summary, warm-up questions, technical quick-check + deep-dive
  questions, thinking questions, teamwork questions, closing notes, and a scoring table.
- Any questions you selected are offered to the model as an optional pool, not a mandatory
  checklist — it picks whichever fit this candidate and the requested interview duration (budgeted
  at roughly 3 minutes per question, plus a short fixed wrap-up) and weaves them into the guide
  with tailored guidance. Your full original selection still appears verbatim at the end of the
  document, under "Additional questions from the Questions DB", as a reference in case it's useful.
- The JSON is validated (pydantic) and rendered into a `.docx` you can download, plus shown on the
  results page. Each guide section shows a recommended time estimate based on its question count.
- Every generated guide is saved under the user who generated it (private per user) and can be
  revisited from "My guides".

## Accounts and roles

There's no public sign-up form — accounts are invite-only, identified by email address:

- **First run**: the app has zero users, so it redirects you to `/setup` to create the first
  account. That account is automatically a superadmin.
- **user**: can generate guides, see their own guide history, and manage their own Own Questions
  DB (create/import/edit/delete their own private question groups and questions).
- **admin**: everything a user can do, plus managing the Shared Questions DB (question groups
  every user can select from when generating), Interview Roles (the role tag list on the generate
  form), and System Prompts.
- **superadmin**: everything an admin can do, plus managing user accounts (create, delete, change
  role) from the "Users" page.
- Passwords are hashed (never stored in plain text). There's no CSRF protection or rate limiting on
  login — fine for an internal tool on your own network, but don't expose this directly to the
  public internet as-is.

## System Prompts

The prompt sent to the LLM is stored in the database, not hardcoded in source — admins manage it
from the System Prompts page. Each prompt has:

- `content`: the instructions and JSON schema sent to the model. Supports `{variable}` placeholders
  (candidate name, role title, duration, research text, curated questions pool) listed on the edit
  page.
- `scoring_rows`: the guaranteed rows of the "Quick evaluation" table at the end of every guide
  (columns are fixed in code; only the rows are configurable here).

When generating, the app uses only whichever prompt you pick on the generate form — there is no
fallback and no built-in default prompt. A fresh install needs at least one System Prompt created
(with real content) before guide generation will work, and generation fails with a clear error if
no prompt is selected.

## Important notes / limitations

- **No default System Prompt, no fallback**: since prompt content is read only from the database
  and only the prompt selected on the generate form is used, generating a guide will fail with a
  clear error until an admin creates at least one System Prompt with non-empty content and it's
  selected (see above).
- **LinkedIn**: there's no supported way to scrape LinkedIn profiles directly (no public API for
  this, and it violates LinkedIn's Terms of Service to scrape while logged in or bypass their login
  wall). This app expects you to paste the profile content yourself, or upload LinkedIn's own "Save
  to PDF" export of the profile. If you later want automated fetching, that would require a paid
  third-party data provider (e.g. Proxycurl) — swap it in inside `interview_app/extractors.py`.
- **LLM keys**: this app does not host its own model. It calls Anthropic's or OpenAI's API using a
  key you provide. Nothing is sent anywhere except to whichever provider you select.
- **Linked pages**: only static/server-rendered page text is extracted (via `requests` +
  BeautifulSoup). Heavy JS single-page apps (some portfolio sites) may return little or no text —
  this is a best-effort signal, not a guarantee.

## Setup

```bash
cd interview-summary-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least one of:
- `ANTHROPIC_API_KEY` (for Claude)
- `OPENAI_API_KEY` (for OpenAI)

`LLM_PROVIDER` picks the default shown in the UI dropdown; you can switch providers per-request
from the form as long as the corresponding key is set.

## Run

```bash
python3 app.py
```

Open http://127.0.0.1:5001 — first run takes you to `/setup` to create the first (superadmin)
account, then log in, create a System Prompt (System Prompts page), optionally set up a question
bank, and generate a guide.

The app defaults to port 5001, not Flask's usual 5000, because on macOS "AirPlay Receiver" listens
on port 5000 by default and returns a confusing HTTP 403 page if a browser hits it instead of the
actual app. Change `FLASK_RUN_PORT` in `.env` if 5001 is taken too.

**If `python3 app.py` fails with `ModuleNotFoundError`**: your virtual environment isn't activated
in the current terminal session (a new terminal window/tab always starts without it active). Run
`source .venv/bin/activate` from inside `interview-summary-app`, then try `python3 app.py` again.
If that still fails, the packages were never installed in that venv — run
`pip install -r requirements.txt` first.

## Project layout

```
app.py                                Flask routes, DB/login init, migrations
interview_app/
  models.py                           User / QuestionGroup / Question / GeneratedGuide /
                                       InterviewRole / SystemPrompt (SQLAlchemy)
  auth.py                             Login/logout, first-run bootstrap, user management
  question_bank.py                    Own Questions DB routes (CRUD, docx import, group preview)
  shared_questions.py                 Shared Questions DB routes (admin-only, same shape)
  question_bank_import.py             Parses an uploaded docx into groups/questions/explanations
  roles.py                            Interview Roles CRUD (admin-only)
  system_prompts.py                   System Prompts CRUD (admin-only)
  extractors.py                       CV/LinkedIn text extraction + link following
  llm_providers.py                    Claude/OpenAI adapter
  prompts.py                          Prompt variable substitution, curated-questions formatting
  schema.py                           Pydantic schema the LLM must return, time estimate helpers
  summarizer.py                       Orchestrates prompt -> LLM -> validated schema
  docx_generator.py                   Renders the schema into the final .docx
templates/                            base.html, login/setup/admin_users, questions.html +
                                       question_group_detail.html (and shared_ equivalents),
                                       roles.html, system_prompts.html + system_prompt_edit.html,
                                       index.html (generate form), result.html, history.html
static/style.css
uploads/                              Temp storage for uploaded files (gitignored)
generated/                            Generated .docx files (gitignored)
data/                                 SQLite database file (app.db), gitignored
```

## Deploying

This was intentionally kept local-only for now. It's a standard Flask app, so it can be
containerized/deployed (e.g. to Railway) later without structural changes — just add a
`Procfile`/start command and set the same env vars in the hosting platform.
