"""init schema

Revision ID: 0001
Revises: 
Create Date: 2025-10-26 17:58:31.911333

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from core_pkg.settings import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT, DB_OWNER_PASSWORD, DB_USER_PASSWORD, DB_READONLY_PASSWORD
from core_pkg.settings import INITIAL_ADMIN_LOGIN, INITIAL_ADMIN_PASSWORD, INITIAL_SYSTEM_LOGIN, INITIAL_SYSTEM_PASSWORD, INITIAL_OPER_LOGIN, INITIAL_OPER_PASSWORD
from core_pkg.dbservices import hash_password

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    print(f"Migrating database: {POSTGRES_DB} on {POSTGRES_HOST}:{POSTGRES_PORT}")
    
    # --- Create roles FIRST ---
    op.execute(f"""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_owner') THEN
            CREATE ROLE db_owner LOGIN PASSWORD '{DB_OWNER_PASSWORD}' INHERIT CREATEDB CREATEROLE;
            RAISE NOTICE 'Created role: db_owner';
        END IF;

        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_user') THEN
            CREATE ROLE db_user LOGIN PASSWORD '{DB_USER_PASSWORD}' INHERIT;
            RAISE NOTICE 'Created role: db_user';
        END IF;

        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_readonly') THEN
            CREATE ROLE db_readonly LOGIN PASSWORD '{DB_READONLY_PASSWORD}' INHERIT;
            ALTER ROLE db_readonly SET default_transaction_read_only = on;
            RAISE NOTICE 'Created role: db_readonly';
        END IF;
    END$$;
    """)

    # --- Database settings ---
    print("Configuring database settings...")
    op.execute(f"""
    ALTER DATABASE "{POSTGRES_DB}" SET timezone = 'UTC';
    ALTER DATABASE "{POSTGRES_DB}" SET statement_timeout = '60s';
    ALTER DATABASE "{POSTGRES_DB}" SET idle_in_transaction_session_timeout = '60s';
    ALTER DATABASE "{POSTGRES_DB}" SET lock_timeout = '5s';
    """)

    print("Setting timezone for database roles...")
    op.execute("""
    ALTER ROLE db_owner SET timezone = 'UTC';
    ALTER ROLE db_user SET timezone = 'UTC';  
    ALTER ROLE db_readonly SET timezone = 'UTC';
    """)

    # --- Schema ownership ---
    print("Setting schema ownership...")
    op.execute("""
    ALTER SCHEMA public OWNER TO db_owner;
    """)

    # --- Extensions ---
    print("Creating extensions...")
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS citext;
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    """)

    # --- Database connection permissions ONLY ---
    print("Granting database connection permissions...")
    op.execute(f"""
    GRANT CONNECT ON DATABASE "{POSTGRES_DB}" TO db_user;
    GRANT CONNECT ON DATABASE "{POSTGRES_DB}" TO db_readonly;
    GRANT USAGE ON SCHEMA public TO db_user;
    GRANT USAGE ON SCHEMA public TO db_readonly;
    """)

    # --- Create tables ---
    print("Creating tables...")
    op.execute("""
    CREATE TABLE "Roles" (
      "role_id" SERIAL PRIMARY KEY,
      "name" varchar NOT NULL UNIQUE,
      "description" varchar,
      "allow_system_config" boolean NOT NULL DEFAULT false,
      "allow_user_management" boolean NOT NULL DEFAULT false,
      "allow_system_control" boolean NOT NULL DEFAULT false,
      "allow_robot_preview" boolean NOT NULL DEFAULT false,
      "allow_manage_operations" boolean NOT NULL DEFAULT false,
      "color" varchar DEFAULT 'bg-grey text-white',
      "created_at" timestamp NOT NULL DEFAULT (now())
    );

    CREATE TABLE "Accessors" (
      "accessor_id" SERIAL PRIMARY KEY,
      "login" citext UNIQUE NOT NULL,
      "name" varchar NOT NULL,
      "description" varchar,
      "role_id" integer NOT NULL REFERENCES "Roles"("role_id") ON DELETE RESTRICT,
      "active" boolean NOT NULL DEFAULT true,
      "password_hash" varchar NOT NULL,
      "created_at" timestamp NOT NULL DEFAULT (now())
    );
    """)

    # --- Create indexes for performance ---
    print("Creating indexes...")
    op.execute("""
    CREATE INDEX idx_accessor_login ON "Accessors"(login);
""")

# --- Insert initial data ---
    print("Inserting initial data...")
    op.execute(f"""
    -- Base roles with granular permissions
    INSERT INTO "Roles" (
        name, 
        description, 
        allow_system_config, 
        allow_user_management, 
        allow_system_control, 
        allow_robot_preview, 
        allow_manage_operations,
        color
    ) VALUES 
        ('admin', 'System administrator with full access', true, true, true, true, true,'bg-red text-white'),
        ('operator', 'Standard user with limited access', false, false, true, false, true,'bg-blue text-white'),
        ('system', 'System account for automated operations', true, false, true, true, true,'bg-purple text-white'),
        ('readonly', 'Read-only access for reporting', false, false, false, false, false,'bg-grey text-white');

    -- System accounts
    INSERT INTO "Accessors" (login, name, role_id, active, password_hash, created_at) VALUES 
        ('{INITIAL_SYSTEM_LOGIN}', 'System Account', 3, true, '{hash_password(INITIAL_SYSTEM_PASSWORD)}', now()),
        ('{INITIAL_ADMIN_LOGIN}', 'Default Admin', 1, true, '{hash_password(INITIAL_ADMIN_PASSWORD)}', now()),
        ('{INITIAL_OPER_LOGIN}', 'Default Operator', 2, true, '{hash_password(INITIAL_OPER_PASSWORD)}', now()),
    -- test accessors
        ('testuser', 'Test User', 2, false, '{hash_password(INITIAL_OPER_PASSWORD)}', now()),
        ('testadmin', 'Test Admin', 1, true, '{hash_password(INITIAL_ADMIN_PASSWORD)}', now());

    """)

    # --- Apply permissions to ALL tables and sequences (must happen AFTER creation) ---
    print("Applying permissions to tables and sequences...")
    op.execute("""
    -- Permissions for db_owner (full access)
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO db_owner;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO db_owner;

    -- Permissions for db_user (read/write)
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_user;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO db_user;
    
    -- Permissions for db_readonly (read-only)
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO db_readonly;
    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO db_readonly;

    -- Default privileges for future objects
    ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO db_user;
    ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO db_user;
    ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public
        GRANT SELECT ON TABLES TO db_readonly;
    ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA public
        GRANT SELECT ON SEQUENCES TO db_readonly;
    """)
    
    print("Migration completed successfully!")


def downgrade() -> None:
    """Downgrade schema."""
    print("Rolling back migration...")
    
    # Drop indexes first
    print("Dropping indexes...")
    op.execute("""
    DROP INDEX IF EXISTS idx_accessor_login;
    """)
    
    # Drop tables in reverse dependency order
    print("Dropping tables...")
    op.execute("""
    DROP TABLE IF EXISTS "Accessors" CASCADE;
    DROP TABLE IF EXISTS "Roles" CASCADE;
    """)

    # Drop extensions
    print("Dropping extensions...")
    op.execute("""
    DROP EXTENSION IF EXISTS "uuid-ossp";
    DROP EXTENSION IF EXISTS citext;
    """)

    # Revoke privileges and drop roles
    print("Dropping roles...")
    op.execute("""
    DO $$
    BEGIN
        -- Revoke privileges first
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_readonly') THEN
            REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_readonly;
            REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM db_readonly;
            REVOKE USAGE ON SCHEMA public FROM db_readonly;
            REVOKE CONNECT ON DATABASE current_database() FROM db_readonly;
            DROP ROLE db_readonly;
        END IF;
        
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_user') THEN
            REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM db_user;
            REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM db_user;
            REVOKE USAGE ON SCHEMA public FROM db_user;
            REVOKE CONNECT ON DATABASE current_database() FROM db_user;
            DROP ROLE db_user;
        END IF;
        
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_owner') THEN
            DROP ROLE db_owner;
        END IF;
    END$$;
    """)
    
    print("Rollback completed!")