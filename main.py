import os
import secrets
import sqlite3
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template, request

from pc_builder.catalog import CATALOG, CATEGORIES
from pc_builder.optimizer import choose_build
from pc_builder.prices import SourceBusy, SourceUnavailable
from pc_builder.manual import ManualError, ManualStore
from pc_builder.admin import register_admin
from pc_builder.budgets import BUDGET_OPTIONS


def create_app(source=None, *, data_dir=None, local_admin=False, admin_password=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 4096
    store = ManualStore(data_dir=data_dir)
    manual_mode = source is None
    app.config.update(SECRET_KEY=os.environ.get('RIGLAB_SESSION_SECRET') or secrets.token_hex(32),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_SECURE=os.environ.get('RIGLAB_COOKIE_SECURE') == '1',
                      LOCAL_ADMIN=local_admin, ADMIN_PASSWORD=admin_password if admin_password is not None else os.environ.get('RIGLAB_ADMIN_PASSWORD'))
    app.extensions['manual_store'] = store
    register_admin(app, store)
    mode = 'manual' if manual_mode else getattr(source, 'mode', 'http')

    @app.get('/')
    def home():
        return render_template('index.html', categories=CATEGORIES, price_mode=mode)

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', price_source='Manuel katalog' if manual_mode else 'Akakçe', price_mode=mode)

    @app.post('/api/build')
    def build():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='invalid_input', message='Bütçeni ve hedef çözünürlüğünü seç.'), 400
        try:
            if isinstance(data.get('budget'), bool):
                raise ValueError
            budget = Decimal(str(data.get('budget')))
            if not budget.is_finite() or budget not in BUDGET_OPTIONS or budget.as_tuple().exponent < -2:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return jsonify(error='invalid_budget', message='Listede bulunan bütçe seçeneklerinden birini seç.'), 400
        resolution = data.get('resolution', '1080p')
        if resolution not in ('1080p', '1440p', '4k'):
            return jsonify(error='invalid_resolution', message='Geçerli bir çözünürlük seç.'), 400
        if manual_mode:
            result = store.recommend(budget, resolution)
            if result is None:
                return jsonify(error='no_matching_build', message='Bu bütçe ve çözünürlük için yayında bir sistem bulunamadı. Yönetim ekranından uygun fiyatlı bir kayıt eklenmeli.', retryable=False), 422
            return jsonify(result)
        try:
            quotes = source.quotes(CATALOG)
        except SourceBusy:
            return jsonify(error='source_busy', message='Fiyatlar şu anda güncelleniyor. Kısa bir süre sonra tekrar dene.'), 429
        except SourceUnavailable as error:
            response = jsonify(error='source_unavailable', message=error.user_message,
                               source_status=error.status_code, retry_after=error.retry_after,
                               retryable=error.retryable)
            response.status_code = 503
            if error.status_code == 429:
                response.headers['Retry-After'] = str(error.retry_after)
            return response
        result = choose_build(CATALOG, quotes, budget, resolution)
        if result is None:
            return jsonify(error='no_matching_build', message='Doğrulayabildiğimiz ilanlarla bu bütçeye uygun, eksiksiz bir kasa bulamadık. Bütçeni değiştir veya daha sonra tekrar dene.'), 422
        return jsonify(result)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error='invalid_input', message='İstek çok büyük.'), 413

    @app.errorhandler(ManualError)
    def manual_error(error):
        return jsonify(error='invalid_catalog', message=str(error)), error.status

    @app.errorhandler(sqlite3.DatabaseError)
    def catalog_storage_error(_error):
        return jsonify(error='storage_error', message='Sistem kayıtlarına erişilemiyor. Veri klasörünün yazma iznini kontrol et.'), 503

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith(('/api/', '/admin')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 10000)))
