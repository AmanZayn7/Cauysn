"""Record the tested Mac runtime versions for the container; never reads .env."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

# Pin direct runtime packages, including the psycopg binary implementation.
# Transitive dependencies are resolved by pip; this is not a full hash lock.
PACKAGES = ('google-genai', 'psycopg', 'psycopg-binary', 'httpx',
            'python-dotenv', 'starlette', 'uvicorn')


def capture():
    pins = []
    for package in PACKAGES:
        try:
            pins.append(f'{package}=={version(package)}')
        except PackageNotFoundError:
            raise SystemExit(f'Missing {package}. Install requirements.web.txt and the existing agent dependencies first.')
    path = Path(__file__).parent / 'requirements.runtime.txt'
    path.write_text('# Direct versions from the tested project environment. No secrets.\n' + '\n'.join(pins) + '\n')
    print('Saved requirements.runtime.txt with seven tested runtime package versions.')
    print('The Gemini model and SDK are unchanged. Commit this file before building Docker.')


if __name__ == '__main__':
    capture()
