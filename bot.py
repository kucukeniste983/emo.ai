#!/usr/bin/env python3
"""Run RIGLAB on the user's own computer, or print a build in the terminal.

    python bot.py
    python bot.py --budget 40000 --resolution 1440p

Network requests originate from the machine running this process. This script
does not change proxies, bypass access controls, or route a hosted website
through a visitor's browser.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
import threading
import webbrowser


def budget_value(value):
    text = value.strip().replace(' ', '')
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', text):
        text = text.replace('.', '')
    try:
        amount = Decimal(text.replace(',', '.'))
        if (not amount.is_finite() or not 15000 <= amount <= 150000
                or amount.as_tuple().exponent < -2):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError('Bütçe 15.000–150.000 TL arasında olmalı.') from None


def port_value(value):
    try:
        port = int(value)
        if not 0 <= port <= 65535:
            raise ValueError
        return port
    except ValueError:
        raise argparse.ArgumentTypeError('Port 0–65535 arasında olmalı; 0 boş bir port seçer.') from None


def arguments(argv=None):
    parser = argparse.ArgumentParser(
        description='RIGLAB yerel botu: fiyat istekleri bu programın çalıştığı bilgisayardan yapılır.',
    )
    parser.add_argument('--budget', type=budget_value, metavar='TL', help='Terminalden sistem önerisi al; örnek: 40000')
    parser.add_argument('--resolution', choices=('1080p', '1440p', '4k'), default='1080p', help='Hedef oyun çözünürlüğü (varsayılan: 1080p)')
    parser.add_argument('--port', type=port_value, default=8765, help='Yerel sitenin portu (varsayılan: 8765)')
    parser.add_argument('--no-browser', action='store_true', help='Tarayıcıyı otomatik açma')
    parser.add_argument('--source', choices=('http', 'browser'), default='http', help='Fiyat okuma yöntemi; BASLAT.cmd gerçek tarayıcıyı seçer')
    parser.add_argument('--output', type=Path, metavar='DOSYA.json', help='Terminalde oluşan sistemi yeni bir JSON dosyasına kaydet')
    args = parser.parse_args(argv)
    if args.output is not None and args.budget is None:
        parser.error('--output için --budget gerekli.')
    return args


def money(value):
    number = f'{Decimal(str(value)):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return number + ' TL'


def make_source(args):
    if args.source == 'browser':
        from pc_builder.browser import BrowserAkakceSource
        return BrowserAkakceSource()
    from pc_builder.prices import AkakceSource
    return AkakceSource()


def run_cli(args, source=None):
    from pc_builder.catalog import CATALOG
    from pc_builder.optimizer import choose_build
    from pc_builder.prices import SourceBusy, SourceUnavailable

    if args.output is not None and args.output.exists():
        print('Bu çıktı dosyası zaten var. Yeni bir dosya adı seç; mevcut dosya değiştirilmedi.', file=sys.stderr)
        return 4
    print('Akakçe ürünleri kontrol ediliyor. Bu işlem yaklaşık bir dakika sürebilir.', flush=True)
    source = source if source is not None else make_source(args)
    try:
        quotes = source.quotes(CATALOG)
    except SourceUnavailable as error:
        print(error.user_message, file=sys.stderr)
        return 2
    except SourceBusy:
        print('Fiyatlar şu anda başka bir istek için güncelleniyor.', file=sys.stderr)
        return 2
    result = choose_build(CATALOG, quotes, args.budget, args.resolution)
    if result is None:
        print('Doğrulanan ilanlarla bu bütçede eksiksiz ve uyumlu bir kasa bulunamadı.', file=sys.stderr)
        return 3
    if args.output is not None:
        try:
            with args.output.open('x', encoding='utf-8') as output:
                json.dump(result, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.write('\n')
        except OSError:
            print('Çıktı dosyası oluşturulamadı; dosya yolunu ve izinleri kontrol et.', file=sys.stderr)
            return 4
    print(f'\nRIGLAB | {args.resolution.upper()} | Bütçe: {money(args.budget)}\n')
    for part in result['parts']:
        print(f"{part['category_name']}: {part['name']}")
        print(f"  {money(part['price'])} | {part['url']}")
    print(f"\nToplam: {money(result['total'])}")
    print(f"Kalan:  {money(result['remaining'])}")
    checked = datetime.fromisoformat(result['oldest_price_check']).astimezone(timezone(timedelta(hours=3)))
    print(f"Fiyat kontrolü: {checked:%d.%m.%Y %H:%M} TSİ")
    print('Kargo, montaj, işletim sistemi ve çevre birimleri dahil değildir. Son fiyat ve stoğu ürün sayfasında kontrol et.')
    if args.output is not None:
        print(f'JSON kaydedildi: {args.output}')
    return 0


def open_browser(url):
    try:
        if webbrowser.open(url, new=2):
            return
    except webbrowser.Error:
        pass
    print('Tarayıcı otomatik açılamadı. Terminaldeki yerel adresi tarayıcına yaz.', flush=True)


def run_web(args, app=None, server_factory=None):
    if app is None:
        from main import create_app
        app = create_app(source=make_source(args))
    if server_factory is None:
        from werkzeug.serving import make_server
        server_factory = make_server
    # Only this computer can connect. No remote origin/CORS access is enabled.
    app.config['TRUSTED_HOSTS'] = ['127.0.0.1', 'localhost']
    try:
        server = server_factory('127.0.0.1', args.port, app, threaded=True)
    except (OSError, SystemExit):
        print('Yerel sunucu başlatılamadı. Port kullanımda olabilir; --port 0 ile boş bir port seçebilirsin.', file=sys.stderr)
        return 4
    with server:
        url = f'http://127.0.0.1:{server.server_port}/'
        print(f'RIGLAB yerel botu çalışıyor: {url}', flush=True)
        print('Fiyat istekleri bu bilgisayardan yapılacak. Durdurmak için Ctrl+C.', flush=True)
        if not args.no_browser:
            threading.Thread(target=open_browser, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nRIGLAB durduruldu.', flush=True)
    return 0


def main(argv=None):
    args = arguments(argv)
    try:
        return run_cli(args) if args.budget is not None else run_web(args)
    except ModuleNotFoundError as error:
        if error.name and error.name.split('.')[0] in {'flask', 'werkzeug', 'requests', 'bs4'}:
            print('Bağımlılıklar eksik. Önce şu komutu çalıştır: python -m pip install -r requirements.txt', file=sys.stderr)
            return 1
        raise
    except KeyboardInterrupt:
        print('\nİşlem iptal edildi.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
