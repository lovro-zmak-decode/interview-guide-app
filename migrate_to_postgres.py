#!/usr/bin/env python3
"""
Migrate local SQLite database to PostgreSQL on Render.

Usage:
    1. Get your DATABASE_URL from Render dashboard
    2. Run: python3 migrate_to_postgres.py <RENDER_DATABASE_URL>
    3. Example: python3 migrate_to_postgres.py postgresql://user:pass@host:5432/db

Before running:
    pip install sqlalchemy psycopg2-binary
"""

import os
import sys
import logging
from sqlalchemy import create_engine, inspect, text, MetaData, Table
from sqlalchemy.pool import StaticPool

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_local_db_url() -> str:
    """Get local SQLite database URL."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "data", "app.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Local database not found at {db_path}")
    return f"sqlite:///{db_path}"


def migrate_data(source_url: str, target_url: str) -> None:
    """Migrate data from SQLite to PostgreSQL."""

    logger.info("Connecting to source database (SQLite)...")
    source_engine = create_engine(
        source_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    logger.info("Connecting to target database (PostgreSQL)...")
    target_engine = create_engine(target_url, echo=False)

    try:
        # Get metadata from both databases
        source_metadata = MetaData()
        source_metadata.reflect(bind=source_engine)

        target_metadata = MetaData()
        target_metadata.reflect(bind=target_engine)

        with source_engine.connect() as source_conn:
            with target_engine.begin() as target_conn:
                tables = list(source_metadata.tables.keys())
                logger.info(f"Found {len(tables)} tables in source database: {', '.join(tables)}")

                # Disable foreign key constraints
                logger.info("Disabling foreign key constraints...")
                target_conn.execute(text("SET session_replication_role = replica"))

                for table_name in sorted(tables):
                    logger.info(f"Migrating table: {table_name}")

                    # Get source table
                    source_table = source_metadata.tables[table_name]

                    # Fetch all data
                    result = source_conn.execute(source_table.select())
                    rows = result.fetchall()

                    if not rows:
                        logger.info(f"  (no data)")
                        continue

                    # Get column names
                    column_names = [col.name for col in source_table.columns]

                    # Delete existing data
                    target_conn.execute(text(f"DELETE FROM {table_name}"))

                    # Insert data into target
                    if table_name in target_metadata.tables:
                        target_table = target_metadata.tables[table_name]
                        for row in rows:
                            values_dict = {}
                            for i, col_name in enumerate(column_names):
                                values_dict[col_name] = row[i]
                            target_conn.execute(target_table.insert().values(**values_dict))

                        logger.info(f"  Inserted {len(rows)} rows")
                    else:
                        logger.warning(f"  Table not found in target database!")

                # Re-enable foreign key constraints
                logger.info("Re-enabling foreign key constraints...")
                target_conn.execute(text("SET session_replication_role = default"))

                # Reset auto-increment sequences
                logger.info("Resetting auto-increment sequences...")
                for table_name in sorted(tables):
                    source_table = source_metadata.tables[table_name]

                    # Find primary key column
                    for col in source_table.columns:
                        if col.primary_key and col.autoincrement:
                            try:
                                # Get max ID
                                max_id = target_conn.execute(
                                    text(f"SELECT MAX({col.name}) FROM {table_name}")
                                ).scalar()

                                if max_id:
                                    seq_name = f"{table_name}_{col.name}_seq"
                                    target_conn.execute(text(f"SELECT setval('{seq_name}', {max_id})"))
                                    logger.info(f"  Reset {seq_name} to {max_id}")
                            except Exception as e:
                                logger.debug(f"Could not reset sequence: {e}")
                            break

        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Verify data in Render PostgreSQL database")
        logger.info("2. Deploy to Render with: git push")
        logger.info("3. Check Render logs to confirm database connection works")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_to_postgres.py <DATABASE_URL>")
        print()
        print("Example:")
        print("  python3 migrate_to_postgres.py postgresql://user:pass@db.render.com:5432/interview_app")
        print()
        print("To get your DATABASE_URL:")
        print("  1. Go to Render.com dashboard")
        print("  2. Select your PostgreSQL database")
        print("  3. Copy the 'Internal Database URL'")
        print("  4. Use it with this script")
        sys.exit(1)

    target_url = sys.argv[1]

    if not target_url.startswith("postgresql://"):
        print("Error: URL must start with 'postgresql://'")
        sys.exit(1)

    try:
        source_url = get_local_db_url()

        # Mask password in logs
        masked_url = target_url.split('@')[0].split('://')[0] + '://***:***@' + target_url.split('@')[1]
        print(f"Source: {source_url}")
        print(f"Target: {masked_url}")
        print()

        confirm = input("Proceed with migration? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Migration cancelled")
            sys.exit(0)

        print()
        migrate_data(source_url, target_url)

    except Exception as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
