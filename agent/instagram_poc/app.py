"""Single-operator loopback UI. No Instagram secret is returned to the browser."""
import hmac
import secrets
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from agent.credentials import AccessError


def create_app(service, operator_password, port=8768):
    app = Flask(__name__)
    app.secret_key = secrets.token_bytes(32)
    app.config.update(MAX_CONTENT_LENGTH=16 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_NAME='instagram_poc',
                      PERMANENT_SESSION_LIFETIME=1800)
    allowed_host = f'127.0.0.1:{port}'

    @app.before_request
    def guard():
        if request.host != allowed_host or request.remote_addr != '127.0.0.1':
            return 'Use the loopback operator address.', 403
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and origin != f'http://{allowed_host}':
                return 'Invalid origin.', 403
            token = request.form.get('csrf', '')
            if not token or not hmac.compare_digest(token, session.get('csrf', '')):
                return 'Invalid form token. Reload the page.', 403

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            # no-referrer turns browser form POST origins into "null", which
            # conflicts with the strict origin check above. Keep local origins
            # intact without disclosing referrers to external sites.
            'Referrer-Policy': 'same-origin', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def protected(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('operator'):
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapped

    def page(message='', error=False):
        try:
            status = service.status()
        except AccessError as exc:
            status = {'posts': []}
            message, error = str(exc), True
        return render_template('settings.html', status=status, message=message, error=error)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        session.setdefault('csrf', secrets.token_urlsafe(32))
        error = ''
        if request.method == 'POST':
            if hmac.compare_digest(request.form.get('password', '').encode(), operator_password.encode()):
                session.clear()
                session.update(operator=True, csrf=secrets.token_urlsafe(32))
                session.permanent = True
                return redirect(url_for('index'))
            error = 'Operator password did not match.'
        return render_template('login.html', error=error)

    @app.get('/')
    @protected
    def index():
        return page()

    @app.post('/action/<action>')
    @protected
    def action(action):
        try:
            if action == 'save':
                service.save_account(request.form.get('username', ''), request.form.get('password', ''))
                message = 'Account details saved encrypted. Connect to verify access.'
            elif action == 'connect':
                service.connect(request.form.get('verification_code', '').strip())
                message = 'Account identity verified. You can now fetch posts.'
            elif action == 'fetch':
                try:
                    limit = int(request.form.get('limit', '12'))
                except ValueError:
                    limit = 0
                result = service.fetch_posts(limit, request.form.get('next_page') == 'yes')
                message = f"Fetched {len(result['items'])} posts. Existing IDs were updated in the PoC cache."
            elif action == 'post':
                service.fetch_post(request.form.get('post_id', ''))
                message = 'Post refreshed from Instagram.'
            elif action == 'download':
                try:
                    index = int(request.form.get('asset_index', '0'))
                except ValueError:
                    index = -1
                result = service.download_media(request.form.get('post_id', ''), index,
                                                request.form.get('thumbnail') == 'yes')
                message = f"Saved {result['bytes']} bytes to private downloads as {result['storage_key']}."
            elif action == 'logout':
                session.clear()
                return redirect(url_for('login'))
            else:
                return 'Unknown action.', 404
            return page(message)
        except AccessError as exc:
            return page(str(exc), True), 400
        except Exception:
            # Never expose framework debug pages, SDK responses or stored secrets.
            return page('The operation could not be completed. Existing saved data was preserved.', True), 500

    @app.get('/posts.json')
    @protected
    def export():
        data = {'schema_version': 1, 'items': service.status()['posts']}
        response = jsonify(data)
        response.headers['Content-Disposition'] = 'attachment; filename=instagram-posts.json'
        return response

    return app
