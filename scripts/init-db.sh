#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=database_name="$POSTGRES_DB" --set=app_password="$APP_DB_PASSWORD" --set=migration_password="$MIGRATION_DB_PASSWORD" <<'SQL'
CREATE ROLE ted_owner LOGIN PASSWORD :'migration_password';
CREATE ROLE ted_app LOGIN PASSWORD :'app_password';
ALTER DATABASE :"database_name" OWNER TO ted_owner;
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO ted_app;
ALTER SCHEMA public OWNER TO ted_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ted_app;
CREATE EXTENSION btree_gist;
ALTER DEFAULT PRIVILEGES FOR ROLE ted_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ted_app;
SQL
