# Architecture

A small Flask application that turns a candidate's CV and LinkedIn profile into a timed,
tailored interview guide with a language model, and then supports running the interview: notes,
grades, recommendations and a summary, for one or several interviewers. Server-rendered pages,
one database, no separate front end build.

## The shape of it

```
browser  <--->  Flask app (app.py + interview_app/)  <--->  database (SQLite locally, PostgreSQL deployed)
                      |
                      +--->  language model (OpenAI or Anthropic), prompts read from the database
```

- `app.py` creates the app through `interview_app.create_app()`, registers the blueprints, and
  holds the main routes: generating a guide, the report page, interview notes, the summary, file
  and Word downloads, and the health check.
- `interview_app/` holds the rest, one module per concern.
- `templates/` (Jinja) and `static/` (one stylesheet) are the whole UI. The report page carries
  its own script for autosave, polling and the interview controls.

## Modules

| Module | Responsibility |
|---|---|
| `__init__.py` | App factory. Requires `FLASK_SECRET_KEY` and `DATABASE_URL`, names the PostgreSQL driver, resolves SQLite paths |
| `models.py` | The tables (below) |
| `auth.py`, `google_auth.py` | Email and password login, invite-only accounts, Google sign-in that reuses an account with the same email |
| `question_bank.py`, `shared_questions.py`, `question_bank_import.py` | Own and shared question groups, import from a Word file |
| `roles.py`, `system_prompts.py` | Interview roles; prompts and their variables (admin) |
| `extractors.py` | Text from PDF, Word and text files; follows a few links found in the CV |
| `llm_providers.py` | One small interface over the OpenAI and Anthropic APIs; model ids from the environment |
| `prompts.py`, `summarizer.py`, `schema.py` | Prompt variables, the two model calls (guide and summary), and the pydantic shapes of their output |
| `interview_log.py` | Everything about a person's notes: shape, validation, merging, what is shareable |
| `storage.py` | The `FileStorage` interface and its database backend |
| `docx_generator.py` | Builds the Word report |

## Data

| Table | Holds |
|---|---|
| `user` | Accounts, with a role: `user`, `admin` or `superadmin` |
| `question_group`, `question` | The question bank. Groups are private to a user or shared |
| `system_prompt` | Prompts, of type `technical` (guide) or `summary` |
| `interview_role` | Suggestions for the role field |
| `generated_guide` | A guide: the structured result as JSON, the extracted source text, the settings it was made with |
| `guide_document` | Metadata of the stored CV and LinkedIn files |
| `stored_file` | The bytes, written only through `FileStorage` |
| `interview_log` | One row per guide and person: answers, own questions, live notes, grades, recommendation, second-round choice, summary |

A guide's owner and admins are its participants. Nobody else can open it.

## Generating a guide

1. The form posts a CV (and optionally a LinkedIn file or pasted text) and settings.
2. `extractors` reads the text; the files are kept through `FileStorage`.
3. The chosen `technical` prompt is rendered with the candidate text, the selected bank questions
   and the additional notes, and sent to the model. The reply is validated against
   `schema.InterviewSummary` and retried once if it is not valid JSON.
4. The guide is stored. Regenerating a guide reuses the stored text and copies its files.

## Running an interview

On the report page a participant presses "Start interview". From then on:

- Notes are saved to their own `interview_log` row, automatically (see
  [ADR 0010](docs/adr/0010-save-interview-notes-automatically-after-30-seconds.md)).
- Other participants' answers, own questions and live notes appear read-only, refreshed by
  polling `/history/<id>/others`.
- A person's scoring is hidden from the others while an interview is in progress and shown when
  both are done ([ADR 0004](docs/adr/0004-hide-scores-only-while-an-interview-is-in-progress.md)).
  This is enforced on the server.
- "End interview" optionally asks the model for a summary from that person's notes, in the
  language of the notes. The second-round choice stays the interviewer's own.
- The Word report contains everyone's notes and scoring.

## Principles

- **The server decides what a browser may see.** Hidden data is never sent and then hidden.
- **User text is only ever text.** It is never inserted as HTML.
- **Nothing that must survive a deploy lives on disk.** Files are in the database, reports are
  rebuilt on demand.
- **Configuration has no unsafe defaults.** Required settings are required.
- **Prompts are data.** They change without a deploy.

## Local topology

`python app.py` serves on http://127.0.0.1:5001 with the Flask debug reloader, against the SQLite
file named in `DATABASE_URL` (default `sqlite:///data/app.db`). Settings come from `.env`.
Tests use a throwaway SQLite file, or any database named in `TEST_DATABASE_URL`.

## Deployed topology

Planned on Railway: gunicorn (`gthread` workers, 180 second timeout) behind Railway's proxy, a
PostgreSQL service, `/healthz` as the health check. See
[docs/runbooks/deployment.md](docs/runbooks/deployment.md). Deployment automation is not defined
yet ([ADR 0015](docs/adr/0015-leave-deployment-automation-for-later.md)).
