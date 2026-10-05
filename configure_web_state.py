"""Manual Neon owner setup for durable web state. Does not change business data."""
import getpass
import os
import sys
import psycopg
from psycopg import sql
from deployment_config import ROOT


def main():
    dsn=os.getenv('CAUSYN_OWNER_DATABASE_URL')
    if not dsn:raise ValueError('Set the owner URL privately in .env first.')
    password=getpass.getpass('Private causyn_web password (at least 24 characters): ')
    if len(password)<24:raise ValueError('Use a randomly generated password of at least 24 characters.')
    if password!=getpass.getpass('Repeat password: '):raise ValueError('Passwords do not match. Nothing changed.')
    with psycopg.connect(dsn,connect_timeout=10) as db:
        if db.execute("SELECT 1 FROM pg_roles WHERE rolname='causyn_web'").fetchone() is None:
            db.execute('CREATE ROLE causyn_web LOGIN')
        db.execute(sql.SQL('ALTER ROLE causyn_web LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
        database=db.execute('SELECT current_database()').fetchone()[0]
        db.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO causyn_web').format(sql.Identifier(database)))
        db.execute('CREATE SCHEMA IF NOT EXISTS app_state AUTHORIZATION causyn_web')
        db.execute('REVOKE ALL ON SCHEMA app_state FROM PUBLIC')
        db.execute('GRANT USAGE ON SCHEMA app_state TO causyn_web')
        for schema in ('raw','staging','analytics'):
            db.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM causyn_web').format(sql.Identifier(schema)))
        db.execute('''CREATE TABLE IF NOT EXISTS app_state.sessions(token TEXT PRIMARY KEY,expires DOUBLE PRECISION NOT NULL);
            CREATE TABLE IF NOT EXISTS app_state.counters(bucket TEXT PRIMARY KEY,amount INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS app_state.logins(bucket TEXT PRIMARY KEY,amount INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS app_state.charts(owner TEXT NOT NULL,name TEXT NOT NULL,
                content TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL,PRIMARY KEY(owner,name));''')
        db.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA app_state TO causyn_web')
    print('PASS: durable web state configured. Business data remains separate and read-only to the agents.')


if __name__=='__main__':
    try:main()
    except (ValueError,psycopg.Error) as error:
        print(str(error) if isinstance(error,ValueError) else 'State setup failed and was rolled back. Check owner privileges and database availability.',file=sys.stderr)
        raise SystemExit(1)
