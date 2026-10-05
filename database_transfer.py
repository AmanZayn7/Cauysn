"""Manual PostgreSQL backup/restore helper. Never called by the server or agents.

Export from the local database; restore only to a target without project schemas.
The owner URL stays in the private environment, not command arguments or output.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import psycopg
from deployment_config import ROOT
from psycopg.conninfo import conninfo_to_dict


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('export', 'restore'))
    parser.add_argument('--file', default=str(ROOT/'causyn.dump'))
    args=parser.parse_args()
    path=Path(args.file).expanduser().resolve()
    executable=shutil.which('pg_dump' if args.operation=='export' else 'pg_restore')
    if not executable:
        raise ValueError('Install PostgreSQL client tools and put pg_dump/pg_restore on PATH.')
    if args.operation=='export':
        if path.exists():
            raise ValueError('Backup already exists. Choose a new filename; nothing was overwritten.')
        # Local owner credentials are separate from the runtime reader.
        options={'host':'localhost','port':'5432','dbname':'causyn','user':os.getenv('USER','aman')}
        if os.getenv('CAUSYN_LOCAL_OWNER_DATABASE_URL'):
            options=conninfo_to_dict(os.environ['CAUSYN_LOCAL_OWNER_DATABASE_URL'])
        path.touch(mode=0o600, exist_ok=False)
        command=[executable,'--format=custom','--no-owner','--no-acl','--schema=raw',
                 '--schema=staging','--schema=analytics','--file',str(path)]
    else:
        if not path.is_file():
            raise ValueError('Backup file does not exist.')
        dsn=os.getenv('CAUSYN_OWNER_DATABASE_URL')
        if not dsn:
            raise ValueError('Set the private CAUSYN_OWNER_DATABASE_URL for the empty hosted target.')
        options=conninfo_to_dict(dsn)
        if options.get('sslmode') not in ('require','verify-ca','verify-full'):
            raise ValueError('The hosted owner URL must explicitly enable TLS.')
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            row=connection.execute("SELECT COUNT(*) FROM pg_namespace WHERE nspname IN ('raw','staging','analytics')").fetchone()
            if row[0]:
                raise ValueError('Target already contains project schemas. Restore stopped to protect existing data.')
        command=[executable,'--no-owner','--no-acl','--exit-on-error','--single-transaction',str(path)]
    environment=os.environ.copy()
    for key in ('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGSSLROOTCERT','PGSERVICE','PGOPTIONS','PGCHANNELBINDING','PGSSLCERT','PGSSLKEY','PGCONNECT_TIMEOUT'):
        environment.pop(key, None)
    mappings={'host':'PGHOST','port':'PGPORT','dbname':'PGDATABASE','user':'PGUSER',
              'password':'PGPASSWORD','sslmode':'PGSSLMODE','sslrootcert':'PGSSLROOTCERT',
              'options':'PGOPTIONS','channel_binding':'PGCHANNELBINDING','sslcert':'PGSSLCERT',
              'sslkey':'PGSSLKEY','connect_timeout':'PGCONNECT_TIMEOUT'}
    for name,key in mappings.items():
        if name in options: environment[key]=options[name]
    if args.operation=='restore':
        command[1:1]=['--dbname',options.get('dbname','causyn')]
    completed=subprocess.run(command,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    if completed.returncode:
        if args.operation=='export': path.unlink(missing_ok=True)
        raise ValueError('PostgreSQL transfer failed. Check client/server versions, private connection settings and target privileges. No credentials were printed.')
    if args.operation=='export': path.chmod(0o600)
    print('PASS: database '+('exported to '+str(path) if args.operation=='export' else 'restored to the empty hosted target')+'.')


if __name__=='__main__':
    try: main()
    except (ValueError,psycopg.Error,OSError) as error:
        print(str(error) if isinstance(error,ValueError) else 'Database transfer failed. Check the private settings and file permissions.',file=sys.stderr)
        raise SystemExit(1)
