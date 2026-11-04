import os
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template, request

from pc_builder.catalog import CATALOG, CATEGORIES
from pc_builder.optimizer import choose_build
from pc_builder.prices import AkakceSource, SourceBusy, SourceUnavailable


def create_app(source=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 4096
    source = source or AkakceSource()

    @app.get('/')
    def home():
        return render_template('index.html', categories=CATEGORIES)

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', price_source='Akakçe')

    @app.post('/api/build')
    def build():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='invalid_input', message='Bütçeni ve hedef çözünürlüğünü seç.'), 400
        try:
            if isinstance(data.get('budget'), bool):
                raise ValueError
            budget = Decimal(str(data.get('budget')))
            if not budget.is_finite() or not 15000 <= budget <= 150000 or budget.as_tuple().exponent < -2:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return jsonify(error='invalid_budget', message='15.000–150.000 TL arasında bir bütçe gir.'), 400
        resolution = data.get('resolution', '1080p')
        if resolution not in ('1080p', '1440p', '4k'):
            return jsonify(error='invalid_resolution', message='Geçerli bir çözünürlük seç.'), 400
        try:
            quotes = source.quotes(CATALOG)
        except SourceBusy:
            return jsonify(error='source_busy', message='Fiyatlar şu anda güncelleniyor. Kısa bir süre sonra tekrar dene.'), 429
        except SourceUnavailable as error:
            response = jsonify(error='source_unavailable', message=error.user_message,
                               source_status=error.status_code, retry_after=error.retry_after,
                               retryable=error.status_code not in (401, 403, 406))
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

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 10000)))
