"""Conservative public-page adapter; it never guesses a price or product URL.

Live selectors/schema still need validation against Akakce after network access
is enabled. Missing or changed structured data makes a product unavailable.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import threading
import time
from urllib.parse import urlencode, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests


BASE = 'https://www.akakce.com'
AGENT = 'Riglab/0.1 (PC comparison prototype)'
HOSTS = {'akakce.com', 'www.akakce.com'}
PRODUCT_PATH = re.compile(r'-fiyati,\d+\.html$')


class SourceUnavailable(Exception):
    def __init__(self, message='Source unavailable', *, status_code=None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def user_message(self):
        if self.status_code in (401, 403, 406):
            return f'Akakçe fiyat isteğini kabul etmedi (HTTP {self.status_code}). Canlı fiyatlar alınamadı; otomatik sorgular durduruldu.'
        if self.status_code == 429:
            return 'Akakçe istek sınırına ulaşıldı (HTTP 429). Fiyatları şu anda güncelleyemiyoruz.'
        return 'Akakçe’nin güncel fiyatlarına şu anda ulaşamıyoruz. Doğrulanmamış fiyatlarla sistem önermiyoruz.'


class SourceBusy(Exception):
    pass


class PageMissing(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    price: Decimal
    url: str
    title: str
    checked_at: str


def safe_url(url, product_only=False):
    try:
        parsed = urlparse(url)
        return (parsed.scheme == 'https' and parsed.hostname in HOSTS
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and (not product_only or bool(PRODUCT_PATH.search(parsed.path))))
    except (ValueError, TypeError):
        return False


def structured_products(document):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if 'Product' in types:
                yield value
            # Only structured graph nodes, never recommendations nested in offers.
            if '@graph' in value:
                yield from walk(value['@graph'])
    for script in document.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue


def parse_quote(html, url, component):
    if not safe_url(url, product_only=True):
        return None
    document = BeautifulSoup(html, 'html.parser')
    for item in structured_products(document):
        title = item.get('name', '')
        if not isinstance(title, str):
            continue
        sku = ' '.join(str(item.get(key, '')) for key in ('sku', 'mpn'))
        if not component.matches(title, sku):
            continue
        offers = item.get('offers', [])
        if isinstance(offers, dict):
            offers = [offers]
        if not isinstance(offers, list):
            continue
        prices = []
        for offer in offers:
            if not isinstance(offer, dict) or offer.get('priceCurrency') != 'TRY':
                continue
            availability = str(offer.get('availability', ''))
            if any(state in availability for state in ('OutOfStock', 'Discontinued', 'SoldOut', 'PreOrder', 'BackOrder')):
                continue
            valid_until = offer.get('priceValidUntil')
            if isinstance(valid_until, str) and valid_until[:10] < datetime.now(timezone.utc).date().isoformat():
                continue
            try:
                price = Decimal(str(offer.get('price', offer.get('lowPrice'))))
                if price.is_finite() and 0 < price < 1000000 and price.as_tuple().exponent >= -2:
                    prices.append(price)
            except (InvalidOperation, ValueError):
                continue
        if prices:
            return Quote(min(prices), url, title, datetime.now(timezone.utc).isoformat())
    return None


class AkakceSource:
    """Per-process cache, one refresh at a time, up to three bounded workers."""
    def __init__(self):
        self._refresh = threading.Lock()
        self._rate = threading.Lock()
        self._cache = {}
        self._cache_at = 0
        self._retry_after = 0
        self._last_request = 0
        self._robots = None
        self._robots_at = 0
        self._interval = 1.0
        self._stop = threading.Event()
        self._deadline = float('inf')
        self._failure = None

    def _read(self, url, robots=False):
        for _ in range(4):
            if self._stop.is_set() or time.monotonic() > self._deadline or not safe_url(url):
                raise SourceUnavailable('Source or destination unavailable')
            if not robots and (self._robots is None or not self._robots.can_fetch('Riglab', url)):
                raise SourceUnavailable('Automated access is not permitted')
            with self._rate:
                wait = self._interval - (time.monotonic() - self._last_request)
                if wait > 0:
                    time.sleep(wait)
                self._last_request = time.monotonic()
            if self._stop.is_set() or time.monotonic() > self._deadline:
                raise SourceUnavailable('Request time budget exhausted')
            try:
                accept = 'text/plain, */*;q=0.5' if robots else 'text/html, application/xhtml+xml, */*;q=0.5'
                with requests.get(url, headers={'User-Agent': AGENT, 'Accept': accept},
                                  timeout=(4, 10), allow_redirects=False, stream=True) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get('Location', ''))
                        continue
                    if response.status_code == 404:
                        raise PageMissing
                    if response.status_code != 200:
                        raise SourceUnavailable(f'Source returned HTTP {response.status_code}', status_code=response.status_code)
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        if time.monotonic() > self._deadline:
                            raise SourceUnavailable('Request time budget exhausted')
                        size += len(chunk)
                        if size > 3_000_000:
                            raise SourceUnavailable('Source response too large')
                        chunks.append(chunk)
                    raw = b''.join(chunks)
                    return raw.decode(response.encoding if response.encoding and response.encoding.lower() != 'iso-8859-1' else 'utf-8', errors='replace'), url
            except requests.RequestException as exc:
                # Never surface upstream exception bodies, headers, or credentials.
                raise SourceUnavailable('Source connection failed') from exc
        raise SourceUnavailable('Too many redirects')

    def _check_robots(self):
        if self._robots and time.monotonic() - self._robots_at < 3600:
            return
        parser = RobotFileParser(BASE + '/robots.txt')
        try:
            text, _ = self._read(BASE + '/robots.txt', robots=True)
        except PageMissing:
            text = ''
        parser.parse(text.splitlines())
        self._interval = max(1.0, parser.crawl_delay('Riglab') or 0)
        if self._interval > 10:
            raise SourceUnavailable('Crawl delay exceeds interactive request budget')
        self._robots, self._robots_at = parser, time.monotonic()

    def _quote(self, component):
        try:
            search_url = BASE + '/arama/?' + urlencode({'q': component.query})
            html, _ = self._read(search_url)
            document = BeautifulSoup(html, 'html.parser')
            candidates = []
            for anchor in document.select('a[href]'):
                url = urljoin(BASE, anchor['href']).split('#')[0]
                if safe_url(url, product_only=True) and url not in candidates:
                    candidates.append(url)
            for url in candidates[:3]:
                try:
                    html, final_url = self._read(url)
                except PageMissing:
                    continue
                quote = parse_quote(html, final_url, component)
                if quote:
                    return component.id, quote
            return component.id, None
        except PageMissing:
            return component.id, None
        except SourceUnavailable:
            self._stop.set()
            raise

    def quotes(self, components):
        if self._cache and time.monotonic() - self._cache_at < 900:
            return dict(self._cache)
        if self._failure is not None and (self._failure.status_code in (401, 403, 406) or time.monotonic() < self._retry_after):
            raise self._failure
        if not self._refresh.acquire(blocking=False):
            raise SourceBusy
        try:
            self._stop.clear()
            started = time.monotonic()
            self._deadline = started + 80
            self._check_robots()
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = dict(pool.map(self._quote, components))
            verified = {key: quote for key, quote in results.items() if quote is not None}
            if not verified:
                raise SourceUnavailable('No supported verified price data')
            self._cache, self._cache_at = verified, started
            self._failure = None
            return dict(verified)
        except SourceUnavailable as error:
            self._failure = error
            self._retry_after = time.monotonic() + 60
            raise
        finally:
            self._refresh.release()
