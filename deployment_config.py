"""Shared local/container settings. Importing never connects to a service."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=False)


def runtime_path(*parts):
    return Path(os.getenv('CAUSYN_RUNTIME_DIR', str(ROOT))).expanduser().resolve().joinpath(*parts)


def database_options():
    # DSN values override local defaults; the password is never printed.
    import psycopg.conninfo
    dsn = os.getenv('DATABASE_URL', '')
    values = psycopg.conninfo.conninfo_to_dict(dsn) if dsn else {}
    options = dict(host='localhost', port='5432', dbname='causyn', user='causyn_reader')
    for name in ('host', 'port', 'dbname', 'user', 'password', 'sslmode', 'sslrootcert'):
        value = os.getenv('CAUSYN_DB_' + name.upper())
        if value:
            options[name] = value
    options.update(values)
    options['connect_timeout'] = 5
    options['application_name'] = 'causyn_reader'
    return options


class WebSettings:
    def __init__(self):
        self.production = os.getenv('CAUSYN_ENV', 'local') == 'production'
        self.port = int(os.getenv('PORT', '8765'))
        self.bind = os.getenv('CAUSYN_BIND', '0.0.0.0' if self.production else '127.0.0.1')
        origin = os.getenv('CAUSYN_PUBLIC_ORIGIN', f'http://127.0.0.1:{self.port}').rstrip('/')
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('http', 'https') or not parsed.netloc or
                parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path):
            raise ValueError('CAUSYN_PUBLIC_ORIGIN must be a single http(s) origin without a path.')
        self.origin = origin
        self.origins = {origin}
        self.hosts = {parsed.netloc}
        if not self.production and parsed.hostname in ('localhost', '127.0.0.1'):
            self.origins.update({f'http://localhost:{self.port}', f'http://127.0.0.1:{self.port}'})
            self.hosts.update({f'localhost:{self.port}', f'127.0.0.1:{self.port}'})
        self.live = os.getenv('CAUSYN_LIVE_ENABLED', 'true' if not self.production else 'false').lower() == 'true'
        self.access_code = os.getenv('CAUSYN_ACCESS_CODE', '')
        self.auth_required = self.production or bool(self.access_code)
        self.daily_limit = int(os.getenv('CAUSYN_DAILY_LIVE_LIMIT', '20'))
        self.session_limit = int(os.getenv('CAUSYN_HOURLY_SESSION_LIMIT', '5'))
        if self.daily_limit < 1 or self.session_limit < 1:
            raise ValueError('Live investigation limits must be positive.')
        if self.production:
            if parsed.scheme != 'https':
                raise ValueError('Production requires an HTTPS CAUSYN_PUBLIC_ORIGIN.')
            if len(self.access_code) < 24:
                raise ValueError('Production requires CAUSYN_ACCESS_CODE of at least 24 characters.')
            if self.live and (not os.getenv('DATABASE_URL') or not os.getenv('GEMINI_API_KEY')):
                raise ValueError('Production Live requires DATABASE_URL and GEMINI_API_KEY.')
            if self.live and database_options().get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
                raise ValueError('Production Live requires an explicit TLS sslmode in DATABASE_URL.')
        self.secure_cookie = parsed.scheme == 'https'
