"""
Main Flask application for Mkulima-Bora backend
"""
import sys
import os

# Add the backend directory to Python path for Vercel deployment
# 
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from flask import Flask, send_from_directory, request, g, has_request_context, abort
from flask_cors import CORS
from config import Config
from routes.auth import auth_bp
from routes.profiles import profiles_bp
from routes.uploads import uploads_bp
from routes.products import products_bp
from routes.support import support_bp
from routes.chat import chat_bp
from routes.cart import cart_bp
from routes.orders import orders_bp
from routes.tenders import tenders_bp
from routes.phone_sharing import phone_bp
from asgiref.wsgi import WsgiToAsgi
import logging
import os
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [req:%(request_id)s] - %(message)s'
)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = (
            getattr(g, 'request_id', '-') if has_request_context() else '-'
        )
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())

app = Flask(__name__)
app.config.from_object(Config)


@app.before_request
def inject_request_id():
    incoming = request.headers.get('X-Request-ID')
    g.request_id = incoming or uuid.uuid4().hex[:12]


@app.after_request
def expose_request_id(resp):
    if hasattr(g, 'request_id'):
        resp.headers['X-Request-ID'] = g.request_id
    return resp

# Enable CORS
CORS(app, origins=Config.CORS_ORIGINS)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profiles_bp)
app.register_blueprint(uploads_bp)
app.register_blueprint(products_bp)
app.register_blueprint(support_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(tenders_bp)
app.register_blueprint(phone_bp)

@app.route('/api/health')
def health():
    """Detailed health check"""
    return {
        'status': 'ok',
        'service': 'Mkulima-Bora Authentication API',
        'version': '1.0.0'
    }, 200


@app.route('/api/public-config')
def public_config():
    """
    Public, non-sensitive feature flags for frontend HTML pages.
    """
    return {
        'gps_enabled': bool(getattr(Config, 'GPS_ENABLED', True)),
    }, 200

@app.route('/assets/<path:filename>')
def serve_assets(filename: str):
    """
    Serve static assets from frontend/assets (paths match HTML: /assets/img/...).
    """
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, 'frontend')
    assets_dir = os.path.join(frontend_dir, 'assets')
    return send_from_directory(assets_dir, filename)

@app.route('/favicon.ico')
def favicon():
    """Browsers request /favicon.ico by default; serve the same logo as pages use."""
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, 'frontend')
    return send_from_directory(
        os.path.join(frontend_dir, 'assets', 'img'),
        'logo.jpeg',
        mimetype='image/jpeg',
    )


def _frontend_dir():
    project_root = os.path.dirname(backend_dir)
    return os.path.join(project_root, 'frontend')


@app.route('/robots.txt')
def robots_txt():
    """Expose robots.txt at site root for crawlers (must not be HTML)."""
    fd = _frontend_dir()
    fp = os.path.join(fd, 'robots.txt')
    if not os.path.isfile(fp):
        abort(404)
    return send_from_directory(fd, 'robots.txt', mimetype='text/plain; charset=utf-8')


@app.route('/sitemap.xml')
def sitemap_xml():
    """Expose sitemap at site root for Search Console."""
    fd = _frontend_dir()
    fp = os.path.join(fd, 'sitemap.xml')
    if not os.path.isfile(fp):
        abort(404)
    return send_from_directory(
        fd,
        'sitemap.xml',
        mimetype='application/xml; charset=utf-8',
    )


# Serve frontend static files
@app.route('/')
def serve_index():
    """Serve frontend index (index.html)"""
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, 'frontend')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:path>')
def serve_frontend(path):
    """Serve frontend files - exclude API routes"""
    # Don't serve API routes through this handler
    if path.startswith('api/'):
        return {'error': 'Not found'}, 404
    
    # Get the project root directory (one level up from backend)
    project_root = os.path.dirname(backend_dir)
    frontend_dir = os.path.join(project_root, 'frontend')
    
    # Check if it's a file in frontend directory
    file_path = os.path.join(frontend_dir, path)
    if os.path.isfile(file_path):
        return send_from_directory(frontend_dir, path)
    
    # Try to serve from frontend/js
    if path.startswith('js/'):
        js_file = os.path.join(frontend_dir, 'js', path[3:])
        if os.path.isfile(js_file):
            return send_from_directory(os.path.join(frontend_dir, 'js'), path[3:])

    # Never serve index.html for non-HTML file requests (e.g. robots.txt was returning the homepage).
    leaf = path.split('/')[-1]
    ext = os.path.splitext(leaf)[1].lower()
    if ext and ext != '.html':
        abort(404)

    # For HTML files that don't exist, serve index.html
    if path.endswith('.html') or '/' not in path:
        return send_from_directory(frontend_dir, 'index.html')
    
    # Default: serve index.html for SPA routing
    return send_from_directory(frontend_dir, 'index.html')

# Wrap Flask app with ASGI adapter for uvicorn
asgi_app = WsgiToAsgi(app)

# Export app for Vercel (Vercel expects 'app' variable)
# For local uvicorn: use 'asgi_app'
# For Vercel: use 'app' (WSGI)

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)

