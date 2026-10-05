"""Read-only preflight. Never prints the connection URL or password."""
import sys
import psycopg
from analytics_tools import connect_database

VIEWS = ('monthly_performance', 'category_monthly', 'seller_monthly', 'state_delivery_monthly')


def check():
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SET LOCAL statement_timeout='10s'")
            cursor.execute('SELECT current_user AS name, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname=current_user')
            role = cursor.fetchone()
            if any(role[field] for field in ('rolsuper', 'rolcreatedb', 'rolcreaterole', 'rolbypassrls')):
                raise ValueError('Runtime role has administrative privileges. Use a restricted reader.')
            for view in VIEWS:
                cursor.execute('SELECT has_table_privilege(current_user, %s, %s) AS permitted',
                               (f'analytics.{view}', 'SELECT'))
                if not cursor.fetchone()['permitted']:
                    raise ValueError(f'Reader lacks SELECT on analytics.{view}.')
            # Check write permissions across all existing project tables and views.
            cursor.execute('''SELECT n.nspname, c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname IN ('raw','staging','analytics') AND c.relkind IN ('r','p','v','m')
                AND (has_table_privilege(current_user,c.oid,'INSERT')
                  OR has_table_privilege(current_user,c.oid,'UPDATE')
                  OR has_table_privilege(current_user,c.oid,'DELETE')
                  OR has_table_privilege(current_user,c.oid,'TRUNCATE'))''')
            if cursor.fetchone():
                raise ValueError('Runtime role can write project data. Remove those grants before hosting.')
            cursor.execute("SELECT SUM(delivered_orders) AS orders, SUM(delivered_merchandise_value) AS value FROM analytics.monthly_performance")
            row = cursor.fetchone()
            from decimal import Decimal
            if row['orders'] != 96211 or row['value'] != Decimal('13181027.13'):
                raise ValueError('Hosted monthly totals differ from the validated project baseline.')
    print('PASS: runtime role is restricted; reporting views and validated totals are available.')


if __name__ == '__main__':
    try:
        check()
    except (ValueError, psycopg.Error) as error:
        message = str(error) if isinstance(error, ValueError) else 'Database preflight failed. Check the private connection settings, TLS and grants.'
        print(message, file=sys.stderr)
        raise SystemExit(1)
