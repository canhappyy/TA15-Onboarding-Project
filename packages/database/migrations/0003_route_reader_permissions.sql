DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clearway_api_readonly') THEN
        CREATE ROLE clearway_api_readonly NOLOGIN;
    END IF;
END
$$;

DO $$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO clearway_api_readonly',
        current_database()
    );
END
$$;
GRANT USAGE ON SCHEMA public TO clearway_api_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO clearway_api_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO clearway_api_readonly;
