"""One-time owner action after restoring the database. Never runs at app startup."""
import getpass
import os
import sys
import psycopg
from psycopg import sql
import deployment_config  # Load the private local .env without overwriting hosted env.


def main():
    dsn=os.getenv('CAUSYN_OWNER_DATABASE_URL')
    if not dsn:
        raise ValueError('Set CAUSYN_OWNER_DATABASE_URL privately. The app must never use this owner URL.')
    password=getpass.getpass('Choose a private causyn_reader password (at least 24 characters): ')
    if len(password)<24:
        raise ValueError('Use a randomly generated password of at least 24 characters.')
    if password!=getpass.getpass('Repeat the reader password: '):
        raise ValueError('Passwords do not match. Nothing changed.')
    with psycopg.connect(dsn,connect_timeout=5) as connection:
        if connection.execute("SELECT 1 FROM pg_roles WHERE rolname='causyn_reader'").fetchone() is None:
            connection.execute('CREATE ROLE causyn_reader LOGIN')
        connection.execute(sql.SQL('ALTER ROLE causyn_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
        connection.execute("ALTER ROLE causyn_reader SET default_transaction_read_only='on'")
        database=connection.execute('SELECT current_database()').fetchone()[0]
        connection.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO causyn_reader').format(sql.Identifier(database)))
        connection.execute('GRANT USAGE ON SCHEMA staging, analytics TO causyn_reader')
        connection.execute('''GRANT SELECT ON staging.orders, staging.order_items, staging.products,
            analytics.monthly_performance, analytics.category_monthly, analytics.seller_monthly,
            analytics.state_delivery_monthly TO causyn_reader''')
    print('PASS: hosted reader configured. Put its private TLS URL in DATABASE_URL, then run check_runtime_database.py.')


if __name__=='__main__':
    try: main()
    except (ValueError,psycopg.Error) as error:
        print(str(error) if isinstance(error,ValueError) else 'Reader setup failed. Check owner permissions and restored schemas; the transaction was rolled back.',file=sys.stderr)
        raise SystemExit(1)
