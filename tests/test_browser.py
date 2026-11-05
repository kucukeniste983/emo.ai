import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from pc_builder.browser import BrowserAkakceSource, BrowserSetupError, PageResponse, proxy_settings
from pc_builder.prices import SourceUnavailable


class BrowserTests(unittest.TestCase):
    def test_response_keeps_exact_status_and_retry_header(self):
        response = PageResponse(429, {'Retry-After': '120'}, b'')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '120')
        self.assertEqual(list(response.iter_content(10)), [])

    def test_browser_is_not_started_during_a_saved_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            source = BrowserAkakceSource(state_dir=directory)
            source._save_cooldown(time.time() + 300)
            with patch.object(source, '_session', side_effect=AssertionError('Unexpected browser launch')):
                with self.assertRaises(SourceUnavailable) as error:
                    source.quotes(())
            self.assertEqual(error.exception.status_code, 429)

    def test_browser_mode_uses_one_thread_for_all_parts(self):
        source = BrowserAkakceSource()
        with patch.object(source, '_quote', side_effect=lambda key: (key, key)) as quote:
            self.assertEqual(source._collect(('a', 'b')), {'a': 'a', 'b': 'b'})
        self.assertEqual(quote.call_count, 2)

    def test_proxy_is_preserved_without_exposing_auth_in_server_url(self):
        with patch.dict('os.environ', {'HTTPS_PROXY': 'http://username:password@proxy.example:8080'}):
            proxy = proxy_settings()
        self.assertEqual(proxy['server'], 'http://proxy.example:8080')
        self.assertEqual(proxy['username'], 'username')
        self.assertEqual(proxy['password'], 'password')

    def test_external_navigation_never_reaches_browser(self):
        source = BrowserAkakceSource()
        source._page = Mock()
        with self.assertRaises(SourceUnavailable):
            source._request('https://untrusted.example/', headers={})
        source._page.goto.assert_not_called()

    def test_bad_proxy_has_an_actionable_error_without_secret_details(self):
        with patch.dict('os.environ', {'HTTPS_PROXY': 'http://secret@example.com:invalid'}):
            with self.assertRaises(BrowserSetupError) as error:
                proxy_settings()
        self.assertNotIn('secret', error.exception.user_message)
        self.assertFalse(error.exception.retryable)


if __name__ == '__main__':
    unittest.main()
