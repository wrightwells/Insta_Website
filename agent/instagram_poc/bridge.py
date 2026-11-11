"""Private control API for the authenticated owner application, never public."""
import argparse
import hmac
import logging
import os
from pathlib import Path
import secrets

from flask import Flask, Response, jsonify, request
from werkzeug.serving import run_simple
from agent.credentials import AccessError, Store
from .service import InstagramService
from .storage import PocStore


def create_bridge(service, control_key):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024

    @app.before_request
    def authenticate():
        given = request.headers.get('Authorization', '').encode()
        if not hmac.compare_digest(given, ('Bearer ' + control_key).encode()):
            return jsonify(error='unauthorized'), 401
        if request.method != 'POST' or request.headers.get('Origin'):
            return jsonify(error='unsupported_request'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.errorhandler(AccessError)
    def access_error(exc):
        return jsonify(error=getattr(exc, 'code', 'storage_error')), 400

    @app.errorhandler(Exception)
    def safe_error(exc):
        return jsonify(error='service_failed'), 503

    @app.post('/v1/<operation>')
    def operation(operation):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='invalid_input'), 400
        if operation == 'status':
            status = service.status()
            # No captions, cached media URLs, cursor or SDK settings in status.
            return jsonify({key: status[key] for key in ('username', 'configured', 'connected', 'account_id', 'verified_at', 'last_fetch_at')})
        if operation == 'account':
            if not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
                return jsonify(error='invalid_input'), 400
            service.save_account(data['username'], data['password'])
            return jsonify(saved=True)
        if operation == 'connect':
            if not isinstance(data.get('verification_code', ''), str):
                return jsonify(error='invalid_input'), 400
            return jsonify(service.connect(data.get('verification_code', '')))
        if operation == 'recent':
            result = service.fetch_posts(data.get('limit', 12))
            for post in result['items']:
                post['assets'] = [{'kind': asset['kind'], 'has_image': bool(asset['image_url'])} for asset in post['assets']]
            return jsonify(result)
        if operation == 'image':
            # Only thumbnails/images cached by the verified account reader.
            result = service.download_media(data.get('post_id'), data.get('asset_index', 0), thumbnail=True)
            path = service.store.data_dir / 'downloads' / result['storage_key']
            try:
                with path.open('rb') as handle:
                    content = handle.read(10 * 1024 * 1024 + 1)
                if len(content) > 10 * 1024 * 1024:
                    return jsonify(error='asset_too_large'), 400
                return Response(content, content_type='application/octet-stream')
            finally:
                path.unlink(missing_ok=True)
        return jsonify(error='unknown_operation'), 404

    return app


def main():
    parser = argparse.ArgumentParser(description='Private Instagram control service')
    parser.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8769)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.local/share/mysite-instagram-poc')
    parser.add_argument('--key-dir', type=Path, default=Path.home() / '.config/mysite-instagram-poc')
    parser.add_argument('--control-dir', type=Path, default=Path.home() / '.local/share/mysite-instagram-control')
    args = parser.parse_args()
    # Shared volume contains only this control capability, never IG credentials.
    Store.private_dir(args.control_dir)
    key_path = args.control_dir / 'control.key'
    if not key_path.exists():
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(secrets.token_urlsafe(48))
    control_key = Store.read_private(key_path, 256).decode().strip()
    if len(control_key) < 48:
        raise SystemExit('Invalid control key.')
    logging.disable(logging.CRITICAL)
    service = InstagramService(PocStore(args.data_dir, args.key_dir))
    print('Private Instagram control service ready. Request and credential logging disabled.', flush=True)
    run_simple(args.host, args.port, create_bridge(service, control_key), threaded=False,
               use_debugger=False, use_reloader=False)


if __name__ == '__main__':
    main()
