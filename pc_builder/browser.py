"""Render public pages in an ordinary, explicitly identified browser.

Uses the same robots checks, allowed destinations, TLS verification, request
limits and persistent Retry-After handling as the HTTP source. No stealth,
personal browser profiles, proxy rotation or challenge solving is used.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import time
from urllib.parse import urlparse

from .prices import AkakceSource, SourceUnavailable, safe_url


class BrowserSetupError(SourceUnavailable):
    @property
    def retryable(self):
        return False

    @property
    def user_message(self):
        return 'Fiyat tarayıcısı başlatılamadı. Windows’ta BASLAT.cmd dosyasını kullan; Edge veya Chrome kurulu olmalı.'


class BrowserVerificationRequired(SourceUnavailable):
    @property
    def retryable(self):
        return False

    @property
    def user_message(self):
        return 'Akakçe bir erişim veya doğrulama ekranı gösterdi. Otomatik fiyat toplama durduruldu; canlı fiyatlar alınamadı.'


def proxy_settings():
    """Preserve the execution environment's proxy, including injected auth."""
    value = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    if not value:
        return None
    try:
        parsed = urlparse(value)
        if not parsed.hostname or parsed.scheme not in ('http', 'https', 'socks5'):
            raise ValueError
        host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
        result = {'server': f'{parsed.scheme}://{host}' + (f':{parsed.port}' if parsed.port else '')}
    except ValueError:
        raise BrowserSetupError('Unsupported proxy configuration') from None
    if parsed.username:
        from urllib.parse import unquote
        result['username'] = unquote(parsed.username)
        result['password'] = unquote(parsed.password or '')
    return result


@dataclass
class PageResponse:
    status_code: int
    headers: dict
    data: bytes
    encoding: str = 'utf-8'

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_content(self, size):
        for start in range(0, len(self.data), size):
            yield self.data[start:start + size]


class BrowserAkakceSource(AkakceSource):
    mode = 'browser'
    refresh_timeout = 105
    def __init__(self, state_dir=None, *, headless=False, executable_path=None):
        super().__init__(state_dir=state_dir)
        self.headless = headless
        self.executable_path = executable_path
        self._page = None

    @contextmanager
    def _session(self):
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            raise BrowserSetupError('Browser dependency missing') from None
        try:
            with sync_playwright() as runtime:
                browser = None
                candidates = ([{'executable_path': self.executable_path}] if self.executable_path else
                              [{'channel': 'msedge'}, {'channel': 'chrome'}])
                if not self.executable_path:
                    for candidate in ('/usr/bin/chromium', '/usr/bin/chromium-browser'):
                        if Path(candidate).is_file():
                            candidates.append({'executable_path': candidate})
                    candidates.append({})
                proxy = proxy_settings()
                for options in candidates:
                    try:
                        browser = runtime.chromium.launch(headless=self.headless, proxy=proxy, **options)
                        break
                    except Error:
                        continue
                if browser is None:
                    raise BrowserSetupError('No supported browser installed')
                try:
                    # Keep the real browser identity and explicitly identify RIGLAB.
                    probe = browser.new_page()
                    agent = probe.evaluate('navigator.userAgent') + ' Riglab/0.1'
                    probe.context.close()
                    context = browser.new_context(user_agent=agent, ignore_https_errors=False)
                    self._page = context.new_page()
                    page = self._page

                    def guard(route):
                        request = route.request
                        if (request.is_navigation_request() and request.frame == page.main_frame
                                and not safe_url(request.url)):
                            route.abort()
                        else:
                            route.continue_()

                    context.route('**/*', guard)
                    yield
                finally:
                    self._page = None
                    browser.close()
        except Error:
            raise SourceUnavailable('Browser could not load source') from None

    def _collect(self, components):
        # Playwright's sync objects must remain on the refresh's calling thread.
        # One visible page also avoids parallel browser navigation requests.
        return dict(self._quote(component) for component in components)

    def _request(self, url, *, headers, **_kwargs):
        if self._page is None:
            raise BrowserSetupError('Browser session not active')
        if not safe_url(url):
            raise SourceUnavailable('Destination not allowed')
        self._page.set_extra_http_headers({key: value for key, value in headers.items() if key.lower() != 'user-agent'})
        remaining = max(1, min(15, self._deadline - time.monotonic()))
        response = self._page.goto(url, wait_until='domcontentloaded', timeout=remaining * 1000)
        if response is None or not safe_url(self._page.url):
            raise SourceUnavailable('Source navigation failed')
        status = response.status
        response_headers = response.all_headers()
        # Do not render or interact with an HTTP refusal/challenge page.
        if status != 200:
            return PageResponse(status, {'Retry-After': response_headers.get('retry-after')}, b'')
        if urlparse(url).path == '/robots.txt':
            data = response.body()
        else:
            title = self._page.title().casefold()
            if any(marker in title for marker in ('just a moment', 'access denied', 'captcha', 'security verification', 'güvenlik doğrulaması', 'erişim engellendi')):
                raise BrowserVerificationRequired('Source requires verification')
            # Wait for DOM-backed products/structured data without network-idle
            # waits on analytics, advertisements or unrelated background traffic.
            from playwright.sync_api import TimeoutError
            try:
                self._page.locator('script[type="application/ld+json"], a[href*="-fiyati,"]').first.wait_for(state='attached', timeout=2000)
            except TimeoutError:
                pass
            data = self._page.content().encode('utf-8')
        if len(data) > 3_000_000:
            raise SourceUnavailable('Source response too large')
        return PageResponse(status, {}, data)
