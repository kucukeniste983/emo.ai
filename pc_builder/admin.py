from functools import wraps
import hmac
import secrets
from urllib.parse import urlparse

from flask import jsonify, redirect, render_template, request, session, url_for

from .manual import MANUAL_CATEGORIES, ManualError
from .budgets import BUDGET_OPTIONS


def register_admin(app, store):
    def local_owner():
        return (app.config.get('LOCAL_ADMIN', False)
                and request.remote_addr in ('127.0.0.1', '::1')
                and urlparse('http://' + request.host).hostname in ('localhost', '127.0.0.1', '::1'))

    def authorized():
        return local_owner() or bool(session.get('admin_authenticated') and app.config.get('ADMIN_PASSWORD'))

    def token():
        if 'admin_csrf' not in session:
            session['admin_csrf'] = secrets.token_urlsafe(32)
        return session['admin_csrf']

    def same_token(value):
        expected = session.get('admin_csrf')
        return isinstance(expected, str) and isinstance(value, str) and hmac.compare_digest(expected.encode(), value.encode())

    def guarded(function):
        @wraps(function)
        def call(*args, **kwargs):
            if not authorized():
                return jsonify(error='unauthorized', message='Yönetim girişi gerekli.'), 401
            if request.method not in ('GET', 'HEAD') and not same_token(request.headers.get('X-CSRF-Token')):
                return jsonify(error='invalid_session', message='Oturum yenilenmeli. Yönetim sayfasını tekrar aç.'), 403
            return function(*args, **kwargs)
        return call

    @app.context_processor
    def owner_context():
        return {'can_manage': authorized(), 'budget_options': BUDGET_OPTIONS}

    @app.before_request
    def admin_body_limit():
        if request.path.startswith('/api/admin/'):
            request.max_content_length = 2 * 1024 * 1024

    @app.get('/admin')
    def admin():
        csrf = token()
        if not authorized():
            return render_template('admin_login.html', csrf=csrf, configured=bool(app.config.get('ADMIN_PASSWORD')), error=None)
        return render_template('admin.html', csrf=csrf, categories=MANUAL_CATEGORIES, local=local_owner())

    @app.post('/admin/login')
    def admin_login():
        configured = app.config.get('ADMIN_PASSWORD')
        candidate = request.form.get('password', '')
        valid = same_token(request.form.get('csrf')) and isinstance(configured, str) and hmac.compare_digest(configured.encode(), candidate.encode())
        if not valid:
            return render_template('admin_login.html', csrf=token(), configured=bool(configured), error='Giriş bilgilerini kontrol et.'), 401
        session.clear()
        session['admin_authenticated'] = True
        token()
        return redirect(url_for('admin'))

    @app.post('/api/admin/logout')
    @guarded
    def admin_logout():
        session.clear()
        return jsonify(ok=True)

    @app.route('/api/admin/systems', methods=['GET', 'POST'])
    @guarded
    def admin_systems():
        if request.method == 'GET':
            return jsonify(systems=store.list())
        return jsonify(system=store.save(request.get_json(silent=True))), 201

    @app.route('/api/admin/systems/<system_id>', methods=['PUT', 'DELETE'])
    @guarded
    def admin_system(system_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ManualError('Sistem bilgileri gerekli.')
        if request.method == 'DELETE':
            store.delete(system_id, payload.get('version'))
            return jsonify(ok=True)
        return jsonify(system=store.save(payload, system_id, payload.get('version')))

    @app.get('/api/admin/export')
    @guarded
    def admin_export():
        response = jsonify(store.export())
        response.headers['Content-Disposition'] = 'attachment; filename="riglab-sistemler.json"'
        return response

    @app.post('/api/admin/import')
    @guarded
    def admin_import():
        return jsonify(imported=store.restore(request.get_json(silent=True)))
