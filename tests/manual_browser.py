"""Exercise manual entry and recommendation with a real browser, offline.

All example records are confined to a temporary database and are deleted at exit.
python tests/manual_browser.py --executable /usr/bin/chromium
"""
import argparse
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

from main import create_app
from pc_builder.catalog import CATEGORIES


def start(directory):
    server = make_server('127.0.0.1', 0, create_app(data_dir=directory, local_admin=True), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f'http://127.0.0.1:{server.server_port}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory, patch('requests.get', side_effect=AssertionError('Unexpected price request')):
        server, thread, base = start(directory)
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(headless=True, **({'executable_path': args.executable} if args.executable else {}))
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                owner = context.new_page()
                errors = []
                owner.on('pageerror', lambda error: errors.append(str(error)))
                owner.goto(base + '/admin')
                expect(owner.locator('#system-count')).to_have_text('0')
                owner.screenshot(path='/tmp/riglab-manual-admin.png', full_page=True)
                owner.set_viewport_size({'width': 390, 'height': 844})
                assert owner.evaluate('document.documentElement.scrollWidth <= innerWidth')
                owner.screenshot(path='/tmp/riglab-manual-admin-mobile.png', full_page=True)
                owner.set_viewport_size({'width': 1440, 'height': 1000})
                owner.locator('#system-name').fill('Test parça sistemi')
                owner.get_by_role('button', name='Taslak kaydet', exact=True).click()
                expect(owner.locator('#system-count')).to_have_text('1')
                check = owner.request.post(base + '/api/build', data={'budget': 35000})
                assert check.status == 422
                for index, (key, label) in enumerate(CATEGORIES.items()):
                    row = owner.locator(f'[data-category="{key}"]')
                    row.locator('.entry-name').fill(label + ' test ürünü')
                    row.locator('.entry-price').fill('4000.25')
                    row.locator('.entry-url').fill(f'https://www.akakce.com/fixture/en-ucuz-test-fiyati,{123450 + index}.html')
                owner.locator('#compatibility-confirmed').check()
                owner.get_by_role('button', name='Kaydet ve yayınla', exact=True).click()
                expect(owner.locator('#admin-notice')).to_contain_text('yayınlandı')
                expect(owner.locator('#system-count')).to_have_text('1')
                consumer = context.new_page()
                consumer.on('pageerror', lambda error: errors.append(str(error)))
                consumer.goto(base + '/')
                consumer.locator('#budget').fill('35000')
                consumer.get_by_role('button', name='Sistemimi oluştur', exact=True).click()
                expect(consumer.locator('#build-result')).to_be_visible()
                expect(consumer.locator('.part-row')).to_have_count(7)
                expect(consumer.locator('#result-title')).to_have_text('Test parça sistemi')
                expect(consumer.locator('#total-price')).to_contain_text('28.001,75')
                expect(consumer.locator('#price-time')).to_contain_text('Kayıt güncellemesi')
                consumer.set_viewport_size({'width': 390, 'height': 844})
                assert consumer.evaluate('document.documentElement.scrollWidth <= innerWidth')
                print('PASS: draft hidden, seven manual parts published, decimal budget total shown, mobile layout fits')

                owner.locator('#new-system').click()
                owner.locator('#system-name').fill('Test hazır sistem')
                owner.locator('#budget-min').fill('50000')
                owner.locator('#budget-max').fill('60000')
                owner.locator('#system-resolution').select_option('1440p')
                owner.locator('#system-kind').select_option('ready')
                owner.locator('#ready-price').fill('55000')
                owner.locator('#ready-url').fill('https://www.akakce.com/fixture/en-ucuz-hazir-fiyati,999999.html')
                owner.locator('#compatibility-confirmed').check()
                owner.get_by_role('button', name='Kaydet ve yayınla', exact=True).click()
                expect(owner.locator('#system-count')).to_have_text('2')
                ready = owner.request.post(base + '/api/build', data={'budget': 55000, 'resolution': '1440p'})
                assert ready.status == 200 and len(ready.json()['parts']) == 1
                backup = owner.request.get(base + '/api/admin/export')
                assert len(backup.json()['systems']) == 2
                assert errors == [], errors
                browser.close()
                print('PASS: ready-system entry, target resolution and two-record backup without external price requests')
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        server, thread, base = start(directory)
        try:
            from urllib.request import Request, urlopen
            import json
            request = Request(base + '/api/build', data=json.dumps({'budget': 55000, 'resolution': '1440p'}).encode(), headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
            assert result['system_name'] == 'Test hazır sistem' and result['total'] == 55000
            print('PASS: restarted application loaded the saved catalog from disk')
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    main()
