#!/bin/bash
set -e

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Railway Database Migration Tool${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}Virtual environment not activated.${NC}"
    echo "Activating venv..."
    source venv/bin/activate
fi

# Check if requirements are installed
if ! python3 -c "import sqlalchemy" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q -r requirements.txt
fi

echo -e "${GREEN}✓ Environment ready${NC}"
echo ""

# Try to get DATABASE_URL from Railway CLI
echo "Checking for Railway CLI..."
if command -v railway &> /dev/null; then
    echo -e "${GREEN}✓ Railway CLI found${NC}"
    echo ""
    echo "Getting DATABASE_URL from Railway..."

    # Try to get the DATABASE_URL
    if DATABASE_URL=$(railway variable get DATABASE_URL 2>/dev/null); then
        echo -e "${GREEN}✓ Found DATABASE_URL from Railway CLI${NC}"
        echo ""
    else
        echo -e "${YELLOW}Could not automatically fetch from Railway CLI${NC}"
        echo "Using manual input instead..."
        DATABASE_URL=""
    fi
else
    echo -e "${YELLOW}Railway CLI not found (optional)${NC}"
    echo "You can install it from: https://docs.railway.app/guides/cli"
    echo ""
fi

# If we don't have DATABASE_URL yet, ask user
if [[ -z "${DATABASE_URL}" ]]; then
    echo -e "${BLUE}Getting your Railway DATABASE_URL:${NC}"
    echo "1. Go to https://railway.app/dashboard"
    echo "2. Open your project"
    echo "3. Click the PostgreSQL service"
    echo "4. Go to the 'Connect' tab"
    echo "5. Copy the DATABASE_URL"
    echo ""
    read -p "Paste your DATABASE_URL here: " DATABASE_URL
fi

# Validate the URL
if [[ ! "${DATABASE_URL}" =~ ^postgresql:// ]]; then
    echo -e "${RED}✗ Invalid DATABASE_URL${NC}"
    echo "Must start with: postgresql://"
    exit 1
fi

# Mask password for display
MASKED_URL=$(echo "${DATABASE_URL}" | sed 's/:.*@/:***:***@/')
echo ""
echo -e "${BLUE}Connection Details:${NC}"
echo "Source: SQLite (data/app.db)"
echo "Target: PostgreSQL (Railway)"
echo "URL: ${MASKED_URL}"
echo ""

# Confirm before proceeding
read -p "Proceed with migration? (yes/no): " confirm
if [[ "${confirm}" != "yes" ]]; then
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting migration...${NC}"
echo ""

# Run the migration script
python3 migrate_to_postgres.py "${DATABASE_URL}"

MIGRATION_RESULT=$?

echo ""
if [ $MIGRATION_RESULT -eq 0 ]; then
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}✓ Migration completed successfully!${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Log in to your Railway app at: https://railway.app/dashboard"
    echo "2. Check the PostgreSQL service for your data"
    echo "3. Deploy your app to Railway (if not already done)"
    echo "4. Visit your app URL to verify data is there"
    echo ""
else
    echo -e "${RED}================================${NC}"
    echo -e "${RED}✗ Migration failed${NC}"
    echo -e "${RED}================================${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "- Check your DATABASE_URL is correct"
    echo "- Verify PostgreSQL service is running in Railway"
    echo "- Check your network connection to Railway"
    exit 1
fi
