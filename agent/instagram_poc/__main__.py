import argparse
import logging
from pathlib import Path
import secrets
from werkzeug.serving import run_simple
from .app import create_app
from .service import InstagramService
from .storage import PocStore


def main():
    parser = argparse.ArgumentParser(description='Local Instagram importer PoC (operator only).')
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.local/share/mysite-instagram-poc')
    parser.add_argument('--key-dir', type=Path, default=Path.home() / '.config/mysite-instagram-poc')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535.')
    store = PocStore(args.data_dir, args.key_dir)
    service = InstagramService(store)
    password = secrets.token_urlsafe(24)
    logging.disable(logging.CRITICAL)
    print(f'Open http://127.0.0.1:{args.port}/', flush=True)
    print(f'Operator password: {password}', flush=True)
    print('Keep this terminal private. Ctrl+C stops the PoC. No requests run until you choose an action.', flush=True)
    app = create_app(service, password, args.port)
    run_simple('127.0.0.1', args.port, app, use_reloader=False, use_debugger=False, threaded=False)


if __name__ == '__main__':
    main()
