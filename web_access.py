"""Persistent sessions, login throttling and atomic Live admission limits.

Single application process/instance. Never stores the access code or API key.
"""
import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class AccessStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS counters(bucket TEXT PRIMARY KEY, amount INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS logins(bucket TEXT PRIMARY KEY, amount INTEGER NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def login_allowed(self, limit=10):
        # Global admission cap avoids trusting spoofable forwarded IP headers.
        # Wrong and successful attempts count. The owner may wait 15 minutes.
        bucket = str(int(time.time() // 900))
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM logins WHERE bucket != ?', (bucket,))
            row = db.execute('SELECT amount FROM logins WHERE bucket=?', (bucket,)).fetchone()
            if row and row[0] >= limit:
                return False
            db.execute('INSERT INTO logins VALUES (?,1) ON CONFLICT(bucket) DO UPDATE SET amount=amount+1', (bucket,))
        return True

    def new_session(self):
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?)', (self.digest(token), time.time() + 21600))
        return token

    def owner(self, token):
        if not token or len(token) > 100:
            return None
        digest = self.digest(token)
        with self.connection() as db:
            row = db.execute('SELECT expires FROM sessions WHERE token=?', (digest,)).fetchone()
        return digest if row and row[0] > time.time() else None

    def logout(self, token):
        if token:
            with self.connection() as db:
                db.execute('DELETE FROM sessions WHERE token=?', (self.digest(token),))

    def admit(self, owner, daily_limit, session_limit):
        day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        hour = str(int(time.time() // 3600))
        buckets = [(f'day:{day}', daily_limit), (f'hour:{hour}:{owner}', session_limit)]
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM counters WHERE bucket NOT LIKE ? AND bucket NOT LIKE ?',
                       (f'day:{day}', f'hour:{hour}:%'))
            for bucket, limit in buckets:
                row = db.execute('SELECT amount FROM counters WHERE bucket=?', (bucket,)).fetchone()
                if row and row[0] >= limit:
                    return False
            for bucket, _ in buckets:
                db.execute('INSERT INTO counters VALUES (?,1) ON CONFLICT(bucket) DO UPDATE SET amount=amount+1', (bucket,))
        return True


class PostgresAccessStore(AccessStore):
    """Durable control state, using a separate role with no business-data access."""
    def __init__(self, dsn):
        # Schema creation is a separate, manual owner action.
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        values=conninfo_to_dict(dsn)
        if values.get('sslmode') not in ('require','verify-ca','verify-full'):
            raise ValueError('CAUSYN_STATE_DATABASE_URL must explicitly enable TLS.')
        if values.get('user') != 'causyn_web':
            raise ValueError('Use causyn_web for the state URL; never the owner or analytics reader.')
        self.dsn=dsn

    @contextmanager
    def connection(self):
        import psycopg
        with psycopg.connect(self.dsn,connect_timeout=10,application_name='causyn_web') as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            yield db

    def login_allowed(self, limit=10):
        bucket=str(int(time.time()//900))
        with self.connection() as db:
            db.execute('SELECT pg_advisory_xact_lock(1129535820)')
            db.execute('DELETE FROM app_state.logins WHERE bucket != %s',(bucket,))
            row=db.execute('SELECT amount FROM app_state.logins WHERE bucket=%s',(bucket,)).fetchone()
            if row and row[0]>=limit:return False
            db.execute('INSERT INTO app_state.logins VALUES (%s,1) ON CONFLICT(bucket) DO UPDATE SET amount=app_state.logins.amount+1',(bucket,))
        return True

    def new_session(self):
        token=secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('DELETE FROM app_state.sessions WHERE expires < %s',(time.time(),))
            db.execute('INSERT INTO app_state.sessions VALUES (%s,%s)',(self.digest(token),time.time()+21600))
        return token

    def owner(self,token):
        if not token or len(token)>100:return None
        digest=self.digest(token)
        with self.connection() as db:
            row=db.execute('SELECT expires FROM app_state.sessions WHERE token=%s',(digest,)).fetchone()
        return digest if row and row[0]>time.time() else None

    def logout(self,token):
        if token:
            with self.connection() as db:
                db.execute('DELETE FROM app_state.sessions WHERE token=%s',(self.digest(token),))

    def admit(self,owner,daily_limit,session_limit):
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        hour=str(int(time.time()//3600))
        buckets=[(f'day:{day}',daily_limit),(f'hour:{hour}:{owner}',session_limit)]
        with self.connection() as db:
            db.execute('SELECT pg_advisory_xact_lock(1129535822)')
            db.execute('DELETE FROM app_state.counters WHERE bucket NOT LIKE %s AND bucket NOT LIKE %s',(f'day:{day}',f'hour:{hour}:%'))
            for bucket,limit in buckets:
                row=db.execute('SELECT amount FROM app_state.counters WHERE bucket=%s',(bucket,)).fetchone()
                if row and row[0]>=limit:return False
            for bucket,_ in buckets:
                db.execute('INSERT INTO app_state.counters VALUES (%s,1) ON CONFLICT(bucket) DO UPDATE SET amount=app_state.counters.amount+1',(bucket,))
        return True

    def save_chart(self,owner,name,content):
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_-]+\.html',name) or len(content.encode())>2_000_000:
            raise ValueError('Invalid chart artifact.')
        with self.connection() as db:
            db.execute('DELETE FROM app_state.charts WHERE expires < %s',(time.time(),))
            db.execute('INSERT INTO app_state.charts VALUES (%s,%s,%s,%s) ON CONFLICT(owner,name) DO UPDATE SET content=EXCLUDED.content, expires=EXCLUDED.expires',
                       (owner,name,content,time.time()+86400))

    def get_chart(self,owner,name):
        with self.connection() as db:
            row=db.execute('SELECT content FROM app_state.charts WHERE owner=%s AND name=%s AND expires>%s',(owner,name,time.time())).fetchone()
        return row[0] if row else None


def create_access_store(path):
    import os
    dsn=os.getenv('CAUSYN_STATE_DATABASE_URL')
    return PostgresAccessStore(dsn) if dsn else AccessStore(path)
