# Database Migration Guide: SQLite to PostgreSQL

This guide explains how to migrate your local SQLite database to PostgreSQL on Render.

## When to Use This

After you've deployed the app to Railway and want to transfer all your existing data from your local SQLite database (`data/app.db`) to the PostgreSQL database on Railway.

## Prerequisites

1. App deployed to Render (see DEPLOY.md)
2. PostgreSQL database created on Render
3. Your DATABASE_URL from Render

## Step 1: Get Your Railway DATABASE_URL

1. Go to [railway.app](https://railway.app) dashboard
2. Open your project
3. Click on the PostgreSQL service
4. Go to the "Connect" tab
5. Copy the **DATABASE_URL** (full connection string)
   - Format: `postgresql://user:password@host:5432/database_name`
6. Keep this handy

## Step 2: Prepare Your Local Environment

```bash
cd /Users/lovrozmak/Decode/candidate-interview-app

# Make sure you have the virtual environment activated
source venv/bin/activate

# Install migration dependencies (should already be there)
pip install -r requirements.txt
```

## Step 3: Run the Migration Script

```bash
python3 migrate_to_postgres.py "postgresql://user:password@host:5432/database_name"
```

Replace the URL with your actual DATABASE_URL from Render.

Example:
```bash
python3 migrate_to_postgres.py "postgresql://interview_user:abc123xyz@db.render.com:5432/interview_app"
```

The script will:
- Show you what's about to happen
- Ask for confirmation (type "yes")
- Copy all tables from SQLite to PostgreSQL
- Transfer all user data, guides, questions, etc.
- Reset auto-increment sequences
- Show completion status

## Step 4: Verify the Migration

After the script completes successfully:

1. **Check the logs**: Script output will show how many rows were transferred
2. **Test locally** (optional):
   - Set `DATABASE_URL` environment variable
   - Run the app locally to test PostgreSQL connection
   ```bash
   export DATABASE_URL="postgresql://user:password@host:5432/database_name"
   python3 app.py
   ```
3. **Check Railway logs**:
   - Go to Railway dashboard
   - Click on your web service
   - View the "Logs" tab
   - Look for database connection confirmations

## What Gets Migrated

The migration copies all data from these tables:

- `user` - all user accounts
- `generated_guide` - all generated interview guides
- `question_group` - custom question groups
- `question` - individual questions
- `system_prompt` - LLM prompts
- `interview_role` - interview role tags
- Any other tables in your database

All relationships and data integrity are preserved.

## Troubleshooting

### "Connection refused" or timeout
- Check if your Render PostgreSQL database is running
- Verify the DATABASE_URL is correct
- Make sure you have network access to Render (not behind a firewall)

### "table does not exist"
- This is normal if the tables haven't been created yet
- Render creates them automatically when the app runs
- Solution: Deploy the app first, then run migration

### "permission denied"
- Check that the username and password in DATABASE_URL are correct
- Verify the user has permission to insert/update data

### Migration stops midway
- Check network connection to Render
- Try running again (script is safe to re-run)
- Check Render PostgreSQL logs for errors

## After Migration

1. **Verify data in Railway**:
   - Log in to your app at the Railway URL
   - Check "My guides" - should show your existing guides
   - Check admin sections - should show your users, questions, prompts

2. **Keep local database as backup**:
   - Your SQLite `data/app.db` is still there
   - Don't delete it unless you're sure everything works

3. **Switch local development to PostgreSQL** (optional):
   - Set `DATABASE_URL` env var in `.env`
   - Your local app will use PostgreSQL instead of SQLite
   - Useful for matching production environment

## Reverting (if needed)

The migration script clears the target table before inserting. If something goes wrong:

1. Delete the PostgreSQL database on Railway (in project settings)
2. Create a new PostgreSQL service
3. Re-run the migration script

Your local SQLite database is never modified, so you can always start over.

## Advanced Options

### Migrate Specific Tables Only

Edit the migration script to add to the `skip_tables` list:

```python
skip_tables = ['user', 'generated_guide']  # Skip these
```

### Migrate to Different Database

The script is generic - you can use it to migrate between any SQLAlchemy-supported databases:

```bash
# SQLite to MySQL
python3 migrate_to_postgres.py "mysql+pymysql://user:pass@host/db"

# SQLite to another Render PostgreSQL instance
python3 migrate_to_postgres.py "postgresql://user:pass@other-host:5432/db"
```

Just install the appropriate driver:
```bash
pip install pymysql  # for MySQL
```

## Questions?

- Check Railway documentation: https://railway.app/docs
- Check migration script comments: `python3 migrate_to_postgres.py`
- Review DEPLOY.md for related deployment info
