"""Generate local development credentials once; never print the password."""
from pathlib import Path
import argparse
import json
import os
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=52773, help='Loopback IRIS host port; use the same IRIS_HOST_PORT for Compose.')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    root = Path(__file__).resolve().parent
    folder = root/'.secrets'
    if folder.is_symlink():
        raise SystemExit('Refusing a symbolic-link credentials directory.')
    folder.mkdir(mode=0o700, exist_ok=True)
    if os.name == 'posix':
        folder.chmod(0o700)
    settings = folder/'instance.json'
    password_file = folder/'iris-password'
    if settings.exists() or password_file.exists():
        raise SystemExit('Local credentials already exist; nothing was overwritten.')
    password = secrets.token_urlsafe(24)
    for path, value in [(password_file, password),
                        (settings, json.dumps({'username': '_SYSTEM', 'password': password,
                                               'base_url': f'http://127.0.0.1:{args.port}'}))]:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
    print('Created local credentials in .secrets/. Keep that directory private.')
    if args.port != 52773:
        print(f'Set IRIS_HOST_PORT={args.port} for Docker Compose to match these settings.')
    print('Next: docker compose up --build -d, then python run_local.py')


if __name__ == '__main__':
    main()
