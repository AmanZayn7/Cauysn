-- Create the reader account if it does not already exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'causyn_reader'
    ) THEN
        CREATE ROLE causyn_reader LOGIN;
    END IF;
END
$$;

ALTER ROLE causyn_reader
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE causyn TO causyn_reader;

GRANT USAGE ON SCHEMA staging, analytics TO causyn_reader;

GRANT SELECT ON
    analytics.monthly_performance,
    staging.orders,
    staging.order_items,
    staging.products
TO causyn_reader;