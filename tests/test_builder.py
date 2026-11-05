"""Synthetic prices are test fixtures only; never served by the application."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import formatdate
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from main import create_app
from pc_builder.catalog import CATALOG
from pc_builder.optimizer import choose_build, compatibility
from pc_builder.prices import AkakceSource, Quote, SourceBusy, SourceUnavailable, parse_quote, retry_delay, round_robin_components, safe_url


INDEX = {part.id: part for part in CATALOG}
URL = 'https://www.akakce.com/ekran-karti/en-ucuz-test-fiyati,12345.html'
NOW = datetime.now(timezone.utc).isoformat()
PARTS = {INDEX[key].category: INDEX[key] for key in ('r5-5600', 'rx6600', 'b550', 'ddr4-16', 'sn580-1', 'cx650', 'ap201')}


def fixture_quotes(parts=CATALOG, price='3000.25'):
    return {part.id: Quote(Decimal(price), URL, part.name, NOW) for part in parts}


class FakeSource:
    def __init__(self, quotes=None, error=None):
        self.values = quotes if quotes is not None else fixture_quotes()
        self.error = error
        self.calls = 0

    def quotes(self, _catalog):
        self.calls += 1
        if self.error:
            raise self.error
        return self.values


class CompatibilityTests(unittest.TestCase):
    def test_known_compatible_configuration(self):
        self.assertTrue(compatibility(PARTS))

    def test_socket_mismatch_is_rejected(self):
        self.assertFalse(compatibility({**PARTS, 'motherboard': INDEX['b650']}))

    def test_ddr_generation_mismatch_is_rejected(self):
        self.assertFalse(compatibility({**PARTS, 'ram': INDEX['ddr5-32']}))

    def test_gpu_must_fit_in_case(self):
        gpu = replace(PARTS['gpu'], specs={**PARTS['gpu'].specs, 'length': 400})
        self.assertFalse(compatibility({**PARTS, 'gpu': gpu}))

    def test_psu_recommendation_and_connectors_are_enforced(self):
        self.assertFalse(compatibility({**PARTS, 'gpu': INDEX['rx7800xt']}))
        self.assertTrue(compatibility({**PARTS, 'gpu': INDEX['rx7800xt'], 'psu': INDEX['cx750']}))
        psu = replace(INDEX['cx750'], specs={**INDEX['cx750'].specs, 'pcie8': 1})
        self.assertFalse(compatibility({**PARTS, 'gpu': INDEX['rx7800xt'], 'psu': psu}))

    def test_no_cpu_cooler_means_no_complete_system(self):
        cpu = replace(PARTS['cpu'], specs={**PARTS['cpu'].specs, 'cooler': False})
        self.assertFalse(compatibility({**PARTS, 'cpu': cpu}))


class OptimizerTests(unittest.TestCase):
    def test_budget_uses_exact_decimal_arithmetic(self):
        result = choose_build(tuple(PARTS.values()), fixture_quotes(PARTS.values()), Decimal('21001.75'))
        self.assertEqual(result['total'], 21001.75)
        self.assertEqual(result['remaining'], 0)
        self.assertEqual(len(result['parts']), 7)
        self.assertIsNone(choose_build(tuple(PARTS.values()), fixture_quotes(PARTS.values()), Decimal('21001.74')))

    def test_missing_component_never_produces_partial_build(self):
        quotes = fixture_quotes()
        for part in CATALOG:
            if part.category == 'psu':
                quotes.pop(part.id)
        self.assertIsNone(choose_build(CATALOG, quotes, 100000))

    def test_selected_full_catalog_build_is_compatible_and_in_budget(self):
        result = choose_build(CATALOG, fixture_quotes(), 25000, '1440p')
        selected = {part['category']: INDEX[part['id']] for part in result['parts']}
        self.assertTrue(compatibility(selected))
        self.assertLessEqual(result['total'], 25000)
        self.assertGreaterEqual(result['remaining'], 0)

    def test_no_verified_prices_means_no_build(self):
        self.assertIsNone(choose_build(CATALOG, {}, 100000))


class ParsingTests(unittest.TestCase):
    def product(self, **offer):
        item = {'@type': 'Product', 'name': 'Sapphire Pulse RX 6600 8 GB Ekran Kartı',
                'offers': {'@type': 'AggregateOffer', 'lowPrice': '9999.90', 'priceCurrency': 'TRY', **offer}}
        return '<script type="application/ld+json">' + json.dumps({'@graph': [item]}) + '</script>'

    def test_verified_product_quote_retains_actual_url(self):
        quote = parse_quote(self.product(), URL, INDEX['rx6600'])
        self.assertEqual(quote.price, Decimal('9999.90'))
        self.assertEqual(quote.url, URL)

    def test_other_product_and_currency_are_rejected(self):
        self.assertIsNone(parse_quote(self.product(), URL, INDEX['rx7600']))
        self.assertIsNone(parse_quote(self.product(priceCurrency='USD'), URL, INDEX['rx6600']))

    def test_no_stock_stale_invalid_and_missing_prices_are_rejected(self):
        for offer in ({'availability': 'https://schema.org/OutOfStock'}, {'priceValidUntil': '2020-01-01'},
                      {'lowPrice': 'NaN'}, {'lowPrice': '-10'}, {'lowPrice': '0'}, {'lowPrice': None}):
            with self.subTest(offer=offer):
                self.assertIsNone(parse_quote(self.product(**offer), URL, INDEX['rx6600']))
        self.assertIsNone(parse_quote('<h1>9.999 TL</h1>', URL, INDEX['rx6600']))

    def test_non_akakce_urls_and_credentials_are_rejected(self):
        for url in ('https://evil.example/item', 'http://www.akakce.com/', 'https://www.akakce.com.evil.example/',
                    'https://user:password@www.akakce.com/', 'https://www.akakce.com:invalid/', 'file:///etc/passwd'):
            with self.subTest(url=url):
                self.assertFalse(safe_url(url))

    def test_boxed_cpu_sku_is_required_for_included_cooler(self):
        self.assertFalse(INDEX['r5-5600'].matches('AMD Ryzen 5 5600', 'tray'))
        self.assertTrue(INDEX['r5-5600'].matches('AMD Ryzen 5 5600', '100-100000927BOX'))

    def test_turkish_gpu_title_is_not_mistaken_for_ti_variant(self):
        self.assertTrue(INDEX['rtx4060'].matches('MSI RTX 4060 Ventus 2X 8 GB Ekran Kartı'))
        self.assertFalse(INDEX['rtx4060'].matches('MSI RTX 4060 Ti Ventus 2X 8 GB Ekran Kartı'))


class SourceTests(unittest.TestCase):
    def test_each_category_is_visited_before_optional_upgrades(self):
        ordered = round_robin_components(CATALOG)
        self.assertEqual(len(ordered), len(CATALOG))
        self.assertEqual(len({part.category for part in ordered[:7]}), 7)
        self.assertEqual({part.id for part in ordered}, {part.id for part in CATALOG})

    def test_retry_after_supports_seconds_dates_and_missing_values(self):
        now = 1800000000
        self.assertEqual(retry_delay('120', now), 120)
        self.assertEqual(retry_delay(formatdate(now + 180, usegmt=True), now), 180)
        self.assertEqual(retry_delay(None, now), 60)
        self.assertEqual(retry_delay('not a date', now), 60)

    def test_429_cooldown_survives_a_new_bot_process(self):
        with tempfile.TemporaryDirectory() as directory:
            source = AkakceSource(state_dir=directory)
            response = Mock(status_code=429, headers={'Retry-After': '300'})
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            with patch('pc_builder.prices.requests.get', return_value=response) as get:
                with self.assertRaises(SourceUnavailable) as first:
                    source.quotes(CATALOG)
                self.assertGreaterEqual(first.exception.retry_after, 299)
                saved = json.loads((Path(directory) / 'akakce-cooldown.json').read_text())
                self.assertGreater(saved['retry_at'], time.time())
                restarted = AkakceSource(state_dir=directory)
                with self.assertRaises(SourceUnavailable) as second:
                    restarted.quotes(CATALOG)
                self.assertEqual(second.exception.status_code, 429)
                self.assertGreaterEqual(second.exception.retry_after, 299)
                get.assert_called_once()

    def test_expired_or_invalid_saved_cooldown_does_not_block_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'akakce-cooldown.json'
            for content in ('not json', json.dumps({'version': 1, 'retry_at': time.time() - 1})):
                file.write_text(content)
                source = AkakceSource(state_dir=directory)
                with patch.object(source, '_check_robots', side_effect=SourceUnavailable) as check:
                    with self.assertRaises(SourceUnavailable):
                        source.quotes(CATALOG)
                    check.assert_called_once()

    def test_robots_txt_requests_plain_text_with_honest_user_agent(self):
        source = AkakceSource()
        response = Mock(status_code=200, encoding='utf-8')
        response.iter_content.return_value = [b'User-agent: *\nAllow: /\n']
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('pc_builder.prices.requests.get', return_value=response) as get:
            source._check_robots()
        headers = get.call_args.kwargs['headers']
        self.assertIn('text/plain', headers['Accept'])
        self.assertIn('Riglab/', headers['User-Agent'])

    def test_refusal_preserves_http_status_and_stops_repeat_requests(self):
        for status in (401, 403, 406):
            with self.subTest(status=status):
                source = AkakceSource()
                response = Mock(status_code=status)
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                with patch('pc_builder.prices.requests.get', return_value=response) as get:
                    with self.assertRaises(SourceUnavailable) as first:
                        source.quotes(CATALOG)
                    self.assertEqual(first.exception.status_code, status)
                    source._retry_after = 0
                    with self.assertRaises(SourceUnavailable) as second:
                        source.quotes(CATALOG)
                    self.assertEqual(second.exception.status_code, status)
                    get.assert_called_once()

    def test_cache_is_reused_without_network(self):
        source = AkakceSource()
        source._cache = fixture_quotes()
        source._cache_at = time.monotonic()
        with patch.object(source, '_read', side_effect=AssertionError('unexpected network')):
            self.assertEqual(source.quotes(CATALOG), fixture_quotes())

    def test_expired_cache_is_not_silently_served_on_failure(self):
        source = AkakceSource()
        source._cache = fixture_quotes()
        source._cache_at = time.monotonic() - 1000
        with patch.object(source, '_check_robots', side_effect=SourceUnavailable):
            with self.assertRaises(SourceUnavailable):
                source.quotes(CATALOG)
        self.assertGreater(source._retry_after, time.monotonic())

    def test_busy_refresh_is_not_duplicated(self):
        source = AkakceSource()
        source._refresh.acquire()
        try:
            with self.assertRaises(SourceBusy):
                source.quotes(CATALOG)
        finally:
            source._refresh.release()


class ApiTests(unittest.TestCase):
    def test_429_exposes_wait_without_leaking_upstream_details(self):
        error = SourceUnavailable('private details', status_code=429, retry_at=time.time() + 120)
        response = create_app(FakeSource(error=error)).test_client().post('/api/build', json={'budget': 40000})
        self.assertEqual(response.json['source_status'], 429)
        self.assertGreaterEqual(response.json['retry_after'], 119)
        self.assertGreaterEqual(int(response.headers['Retry-After']), 119)
        self.assertNotIn('private', response.json['message'])

    def test_406_is_explained_and_not_marked_retryable(self):
        error = SourceUnavailable('private details', status_code=406)
        client = create_app(FakeSource(error=error)).test_client()
        response = client.post('/api/build', json={'budget': 40000})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['source_status'], 406)
        self.assertFalse(response.json['retryable'])
        self.assertIn('406', response.json['message'])
        self.assertNotIn('private', response.json['message'])

    def test_valid_request_returns_full_build(self):
        client = create_app(FakeSource()).test_client()
        response = client.post('/api/build', json={'budget': 40000, 'resolution': '1440p'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['parts']), 7)
        self.assertLessEqual(response.json['total'], 40000)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_invalid_input_never_calls_source(self):
        source = FakeSource()
        client = create_app(source).test_client()
        for value in (None, [], {}, {'budget': True}, {'budget': 'NaN'}, {'budget': 'Infinity'},
                      {'budget': 14999}, {'budget': 150001}, {'budget': '20000.001'},
                      {'budget': 40000, 'resolution': 'invalid'}):
            with self.subTest(value=value):
                response = client.post('/api/build', data=json.dumps(value), content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(source.calls, 0)

    def test_source_error_does_not_leak_details_or_invent_parts(self):
        client = create_app(FakeSource(error=SourceUnavailable('sensitive upstream details'))).test_client()
        response = client.post('/api/build', json={'budget': 40000})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error'], 'source_unavailable')
        self.assertNotIn('parts', response.json)
        self.assertNotIn('sensitive', response.get_data(as_text=True))

    def test_missing_parts_and_busy_source_have_distinct_responses(self):
        for source, code in ((FakeSource(quotes={}), 422), (FakeSource(error=SourceBusy()), 429)):
            client = create_app(source).test_client()
            self.assertEqual(client.post('/api/build', json={'budget': 40000}).status_code, code)

    def test_page_and_assets_load(self):
        client = create_app(FakeSource()).test_client()
        for path in ('/', '/static/style.css', '/static/app.js', '/static/rig.svg'):
            with self.subTest(path=path):
                with client.get(path) as response:
                    self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
