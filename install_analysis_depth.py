"""Create the reporting views as the database owner; never called by an agent."""
import argparse
import getpass
from pathlib import Path
import sys

if __name__=='__main__':
    import psycopg
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user',default=getpass.getuser())
    parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=5432)
    parser.add_argument('--dbname',default='causyn')
    args=parser.parse_args()
    sql=(Path(__file__).parent/'sql'/'06_analysis_depth.sql').read_text()
    # The SQL script supplies its own BEGIN/COMMIT and rolls back on failure.
    try:
        with psycopg.connect(host=args.host,port=args.port,dbname=args.dbname,user=args.user,autocommit=True) as connection:
            connection.execute(sql)
        print('Created 3 reporting views and granted read-only access to causyn_reader.')
        print('Next: ./.venv/bin/python evaluate_depth.py --database')
    except psycopg.Error as error:
        print('Installation failed; check the owner connection and scripts 01-05.',file=sys.stderr)
        print(str(error),file=sys.stderr)
        sys.exit(1)
