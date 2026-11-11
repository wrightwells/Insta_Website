"""Serve only the reviewed policy; no website proxy, credentials, or directory listing."""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

FALLBACK_POLICY = Path('/policy/privacy.html').read_bytes()
POLICY_EXPORT = Path(os.environ.get('POLICY_EXPORT_FILE', '/policy-export/privacy.html'))
POLICY_CSS = Path('/policy/policy.css').read_bytes()
ROBOTS = b'User-agent: *\nAllow: /privacy/\nDisallow: /\n'


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def do_GET(self):
        self.respond()

    def do_HEAD(self):
        self.respond(head=True)

    def respond(self, head=False):
        path = urlsplit(self.path).path
        status, body, content_type = 404, b'Not found\n', 'text/plain; charset=utf-8'
        if path == '/privacy/':
            try:
                body = POLICY_EXPORT.read_bytes()
            except OSError:
                body = FALLBACK_POLICY
            status, content_type = 200, 'text/html; charset=utf-8'
        elif path == '/static/public/policy.css':
            status, body, content_type = 200, POLICY_CSS, 'text/css; charset=utf-8'
        elif path == '/robots.txt':
            status, body = 200, ROBOTS
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
