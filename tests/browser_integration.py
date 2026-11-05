"""Real browser test with synthetic pages only; no live Akakce request is sent.

python tests/browser_integration.py --executable /usr/bin/chromium
"""
import argparse
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_builder.browser import BrowserAkakceSource
from pc_builder.catalog import CATALOG
from pc_builder.optimizer import choose_build
from pc_builder.prices import SourceUnavailable


INDEX = {part.id: part for part in CATALOG}
PARTS = tuple(INDEX[key] for key in ('r5-5600', 'rx6600', 'b550', 'ddr4-16', 'sn580-1', 'cx650', 'ap201'))


class FixtureBrowser(BrowserAkakceSource):
    refusal = None
    seen = []

    @contextmanager
    def _session(self):
        with super()._session():
            urls = {part.query: f'/fixture/en-ucuz-{part.id}-fiyati,{10000 + index}.html'
                    for index, part in enumerate(PARTS)}
            by_path = {urls[part.query]: part for part in PARTS}

            def respond(route):
                parsed = urlparse(route.request.url)
                self.seen.append(parsed.path)
                if self.refusal:
                    route.fulfill(status=self.refusal, headers={'Retry-After': '300'}, body='Source refused')
                    return
                if parsed.path == '/robots.txt':
                    route.fulfill(content_type='text/plain', body='User-agent: *\nAllow: /\n')
                    return
                if parsed.path == '/arama/':
                    path = urls[parse_qs(parsed.query)['q'][0]]
                    markup = '<script>setTimeout(() => {const a=document.createElement("a"); a.href=' + json.dumps(path) + '; a.textContent="Fixture product"; document.body.append(a);}, 50);</script>'
                else:
                    part = by_path[parsed.path]
                    item = {'@type': 'Product', 'name': part.name, 'sku': ' '.join(part.required),
                            'offers': {'@type': 'Offer', 'price': '3000.25', 'priceCurrency': 'TRY'}}
                    markup = '<script>setTimeout(() => {const s=document.createElement("script");s.type="application/ld+json";s.textContent=' + json.dumps(json.dumps(item)) + ';document.head.append(s);}, 50);</script>'
                route.fulfill(content_type='text/html', body='<!doctype html><html><head><title>Fixture</title></head><body>' + markup + '</body></html>')

            self._page.context.route('https://www.akakce.com/**', respond)
            assert 'Riglab/0.1' in self._page.evaluate('navigator.userAgent')
            yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        source = FixtureBrowser(state_dir=directory, headless=True, executable_path=args.executable)
        quotes = source.quotes(PARTS)
        assert len(quotes) == 7
        result = choose_build(PARTS, quotes, Decimal('40000'))
        assert len(result['parts']) == 7 and result['total'] == 21001.75
        assert all('www.akakce.com' in part['url'] for part in result['parts'])
        print('PASS: real Chromium rendered JavaScript-only products and prices into a compatible seven-part fixture build')
    with tempfile.TemporaryDirectory() as directory:
        refused = FixtureBrowser(state_dir=directory, headless=True, executable_path=args.executable)
        refused.refusal = 429
        try:
            refused.quotes(PARTS)
            raise AssertionError('429 was ignored')
        except SourceUnavailable as error:
            assert error.status_code == 429 and error.retry_after >= 299
        restarted = FixtureBrowser(state_dir=directory, headless=True, executable_path=args.executable)
        # If a browser is launched after restart this raises; it must use saved cooldown.
        restarted._session = lambda: (_ for _ in ()).throw(AssertionError('Cooldown bypassed'))
        try:
            restarted.quotes(PARTS)
            raise AssertionError('Saved cooldown was ignored')
        except SourceUnavailable as error:
            assert error.status_code == 429
        print('PASS: browser HTTP 429 preserved and cooldown prevented another browser launch after restart')
    print('LIVE AKAKCE ACCESS: NOT VERIFIED; all content in this test was synthetic')


if __name__ == '__main__':
    main()
