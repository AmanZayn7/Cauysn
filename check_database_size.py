"""Read-only size check before Neon migration. No Gemini requests."""
import sys
import psycopg
from analytics_tools import connect_database

if __name__=='__main__':
    try:
        with connect_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute('SELECT pg_database_size(current_database()) AS bytes, current_setting(\'server_version\') AS version')
                result=cursor.fetchone()
        size=result['bytes']
        print(f"Database size: {size/1024**2:.2f} MiB ({size:,} bytes)")
        print('PostgreSQL version:',result['version'])
        print('Neon published free storage allowance: 1 GB per project; verify the console allowance.')
        print('Comfortably under 1 GB with state headroom.' if size<750_000_000 else 'Close to/above free storage allowance; assess before restoring.')
    except psycopg.Error:
        print('Size check failed. Check the existing local database connection.',file=sys.stderr)
        raise SystemExit(1)
