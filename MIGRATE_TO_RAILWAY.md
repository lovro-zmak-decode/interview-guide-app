# Migrate Your Data to Railway

Quick guide for transferring your local SQLite database to Railway PostgreSQL.

## Prerequisites

- App deployed on Railway (see RAILWAY_QUICK_START.md)
- PostgreSQL database created in Railway
- Access to Railway dashboard

## Option 1: Automated Script (Easiest)

### Step 1: Install Railway CLI (Optional)

For automatic DATABASE_URL fetching:

```bash
# macOS
brew install railway

# Linux/Windows
npm install -g @railway/cli
```

Then login:
```bash
railway login
```

### Step 2: Run Migration Script

```bash
cd /Users/lovrozmak/Decode/candidate-interview-app
source venv/bin/activate
./migrate_to_railway.sh
```

The script will:
- Try to fetch DATABASE_URL from Railway CLI automatically
- Ask you to paste it if not found
- Show what will be migrated
- Ask for confirmation
- Run the migration
- Show results

## Option 2: Manual Migration

### Step 1: Get Your DATABASE_URL

1. Open [railway.app/dashboard](https://railway.app/dashboard)
2. Click your project
3. Click the **PostgreSQL** service
4. Go to the **Connect** tab
5. Copy the full **DATABASE_URL** (it looks like: `postgresql://user:pass@host:5432/db`)

### Step 2: Run Python Script

```bash
cd /Users/lovrozmak/Decode/candidate-interview-app
source venv/bin/activate
python3 migrate_to_postgres.py "postgresql://user:pass@host:5432/db"
```

Replace the URL with your actual DATABASE_URL from Railway.

### Step 3: Confirm & Wait

- Type "yes" when prompted
- Wait for migration to complete
- Script will show which tables were migrated and row counts

## What Gets Migrated

- `user` - All user accounts
- `generated_guide` - All interview guides you generated
- `question_group` - Your custom question groups
- `question` - Your questions
- `system_prompt` - Your LLM prompts
- `interview_role` - Interview role tags

All data relationships and sequences are preserved.

## Verify Migration Worked

### 1. Check Script Output

You should see output like:
```
Migrating table: user
  Inserted 2 rows
Migrating table: generated_guide
  Inserted 5 rows
...
Migration completed successfully!
```

### 2. Test Your App

Visit your Railway app URL and:
- Log in (should work if users were migrated)
- Check "My guides" (should show your existing guides)
- Check admin sections (questions, roles, prompts)

### 3. Check Railway Logs (Optional)

In Railway dashboard:
1. Click your web service
2. Go to "Logs" tab
3. Should see database connections working

## Troubleshooting

### "Connection refused"
- Verify DATABASE_URL is correct
- Check PostgreSQL service is running in Railway
- Make sure you're using the **internal** URL (not external)

### "permission denied"
- Check database user and password in URL
- Verify user has insert/update permissions

### "table does not exist"
- Normal if this is first migration
- Make sure app ran once (creates schema automatically)
- Check with Railway team if PostgreSQL service created successfully

### Script hangs or times out
- Check network connection to Railway
- Try running again
- Check Railway PostgreSQL service status

### Only partial data migrated
- Script is safe to re-run
- It clears target table before inserting
- Your local SQLite is never modified

## After Migration

1. **Keep local database as backup**
   - Don't delete `data/app.db` yet
   - It's still your local copy

2. **Optional: Use PostgreSQL locally**
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:5432/db"
   python3 app.py
   ```
   This makes your local app use the same database as production.

3. **Deploy to Railway**
   - Push any commits: `git push origin main`
   - Railway auto-deploys
   - Your app now uses the migrated data

## Rolling Back

If something goes wrong:

1. **Delete PostgreSQL service** in Railway dashboard
2. **Create new PostgreSQL service**
3. **Re-run the migration script**

Your local SQLite (`data/app.db`) is never touched, so you can always start over.

## Need Help?

- **Script help**: `./migrate_to_railway.sh` (shows instructions)
- **Python migration**: `python3 migrate_to_postgres.py --help`
- **Railway docs**: https://railway.app/docs
- **Railway support**: https://discord.gg/railway

## Quick Command Reference

```bash
# Activate environment
source venv/bin/activate

# Run automated migration
./migrate_to_railway.sh

# Run manual migration
python3 migrate_to_postgres.py "postgresql://..."

# Check migration script options
python3 migrate_to_postgres.py
```
