#!/usr/bin/env python3
"""
Script to check if database migrations have been run and execute them if needed.
"""
import sys
import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from core_pkg.settings import POSTGRES_DB_URL
import time


def check_migration_status():
    """
    Check if the database has been initialized with migrations.
    Returns True if migrations have been run, False otherwise.
    """
    try:
        engine = create_engine(POSTGRES_DB_URL)
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("Migration table 'alembic_version' not found - migrations need to be run")
                return False
            
            # Check if there's a version in the alembic_version table
            result = conn.execute(text("SELECT version_num FROM alembic_version;"))
            version = result.scalar()
            
            if version:
                print(f"Database already migrated to version: {version}")
                return True
            else:
                print("Migration table exists but is empty - migrations need to be run")
                return False
                
    except OperationalError as e:
        print(f"Cannot connect to database: {e}")
        time.sleep(20)  # Wait before retrying
        sys.exit(1)
    except Exception as e:
        print(f"Error checking migration status: {e}")
        time.sleep(20) 
        sys.exit(1)


def run_migrations():
    """
    Run Alembic migrations to upgrade the database to the latest version.
    """
    print("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print("Migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Migration failed with exit code {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        time.sleep(20) 
        sys.exit(1)
    except FileNotFoundError:
        print("Alembic command not found. Make sure alembic is installed.")
        time.sleep(20) 
        sys.exit(1)


def main():
    """
    Main function to check and run migrations if needed.
    """
    print("=" * 60)
    print("DATABASE MIGRATION CHECK")
    print("=" * 60)
    
    if not check_migration_status():
        run_migrations()
    else:
        print("No migration needed - database is up to date")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
