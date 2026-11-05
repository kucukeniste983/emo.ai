"""All records, links and prices below are synthetic fixtures in temporary DBs."""
from copy import deepcopy
from decimal import Decimal
import re
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

from main import create_app
from pc_builder.catalog import CATEGORIES
from pc_builder.manual import ManualError, ManualStore, normalize


URL = 'https://www.akakce.com/islemci/en-ucuz-fixture-fiyati,12345.html'


def record(**changes):
    value = {'name': 'Test oyun sistemi', 'kind': 'parts', 'budget_min': '20000', 'budget_max': '40000',
             'resolution': 'any', 'priority': 50, 'enabled': True, 'compatibility_confirmed': True, 'notes': '',
             'parts': [{'category': key, 'name': label + ' test ürünü', 'price': '3000.25', 'url': URL} for key, label in CATEGORIES.items()]}
    value.update(changes)
    return value


class ManualStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = ManualStore(self.directory.name)

    def test_draft_persists_after_store_restart_and_is_never_recommended(self):
        saved = self.store.save(record(enabled=False, compatibility_confirmed=False, parts=[]))
        restarted = ManualStore(self.directory.name)
        self.assertEqual(restarted.list()[0]['id'], saved['id'])
        self.assertIsNone(restarted.recommend(Decimal('40000'), '1080p'))

    def test_parts_need_all_required_fields_and_owner_confirmation_to_publish(self):
        for payload in (record(parts=[]), record(parts=record()['parts'][:6]), record(compatibility_confirmed=False)):
            with self.subTest(payload=payload), self.assertRaises(ManualError):
                self.store.save(payload)
        self.assertEqual(self.store.list(), [])

    def test_ready_system_can_use_one_manual_link(self):
        payload = record(kind='ready', parts=[{'category': 'system', 'name': 'Hazır test kasa', 'price': '25000', 'url': URL}])
        self.store.save(payload)
        result = self.store.recommend(Decimal('30000'), '1440p')
        self.assertEqual(len(result['parts']), 1)
        self.assertEqual(result['total'], 25000)
        self.assertEqual(result['remaining'], 5000)

    def test_total_and_remaining_use_decimal_and_budget_never_exceeded(self):
        self.store.save(record())
        self.assertIsNone(self.store.recommend(Decimal('21001.74'), '1080p'))
        result = self.store.recommend(Decimal('21001.75'), '1080p')
        self.assertEqual(result['total'], 21001.75)
        self.assertEqual(result['remaining'], 0)
        self.assertEqual(len(result['parts']), 7)
        self.assertEqual(result['mode'], 'manual')
        self.assertIn('elle girildi', result['warnings'][0])

    def test_budget_range_resolution_priority_and_published_state_are_respected(self):
        first = self.store.save(record(priority=10, resolution='1080p', name='İlk'))
        best = self.store.save(record(priority=90, resolution='1440p', name='Öncelikli'))
        self.store.save(record(priority=100, enabled=False, name='Taslak'))
        self.assertEqual(self.store.recommend(Decimal('30000'), '1080p')['id'], first['id'])
        self.assertEqual(self.store.recommend(Decimal('30000'), '1440p')['id'], best['id'])
        self.assertIsNone(self.store.recommend(Decimal('40000.01'), '1080p'))
        self.assertIsNone(self.store.recommend(Decimal('19999'), '1080p'))
        self.assertIsNone(self.store.recommend(Decimal('30000'), '4k'))

    def test_edit_conflict_and_unpublish_and_delete(self):
        saved = self.store.save(record())
        changed = self.store.save(record(name='Yeni ad', enabled=False), saved['id'], saved['version'])
        self.assertEqual(changed['version'], 2)
        self.assertIsNone(self.store.recommend(Decimal('30000'), '1080p'))
        with self.assertRaises(ManualError) as conflict:
            self.store.save(record(), saved['id'], 1)
        self.assertEqual(conflict.exception.status, 409)
        with self.assertRaises(ManualError):
            self.store.delete(saved['id'], 1)
        self.store.delete(saved['id'], 2)
        self.assertEqual(self.store.list(), [])

    def test_export_restore_is_atomic_and_does_not_duplicate_ids(self):
        self.store.save(record())
        archive = self.store.export()
        self.store.restore(archive)
        self.assertEqual(len(self.store.list()), 1)
        bad = deepcopy(archive)
        bad['systems'].append(record(name='', enabled=False))
        before = self.store.export()
        with self.assertRaises(ManualError):
            self.store.restore(bad)
        self.assertEqual(before, self.store.export())

    def test_invalid_prices_and_untrusted_links_are_rejected(self):
        for price in ('NaN', '-1', True, '1.001'):
            payload = record()
            payload['parts'][0]['price'] = price
            with self.subTest(price=price), self.assertRaises(ManualError):
                normalize(payload)
        for url in ('javascript:alert(1)', 'https://www.akakce.com.evil.example/foo', 'https://user:pass@www.akakce.com/foo', 'https://www.akakce.com/'):
            payload = record()
            payload['parts'][0]['url'] = url
            with self.subTest(url=url), self.assertRaises(ManualError):
                normalize(payload)

    def test_total_above_upper_budget_and_duplicate_categories_are_rejected(self):
        with self.assertRaises(ManualError):
            normalize(record(budget_min='1000', budget_max='10000'))
        payload = record()
        payload['parts'][1]['category'] = payload['parts'][0]['category']
        with self.assertRaises(ManualError):
            normalize(payload)


class ManualApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(data_dir=self.directory.name, local_admin=True)
        self.client = self.app.test_client()
        page = self.client.get('/admin')
        self.token = re.search(r'name="csrf-token" content="([^"]+)"', page.get_data(as_text=True)).group(1)
        self.headers = {'X-CSRF-Token': self.token}

    def test_public_and_admin_only_offer_the_requested_budget_options(self):
        expected = [20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000,
                    100000, 120000, 140000, 160000, 200000, 250000]
        public = BeautifulSoup(self.client.get('/').data, 'html.parser')
        self.assertEqual([int(option['value']) for option in public.select('#budget option')], expected)
        self.assertIsNone(public.select_one('#budget-range'))
        self.assertEqual(public.select_one('#budget').name, 'select')
        admin = BeautifulSoup(self.client.get('/admin').data, 'html.parser')
        for selector in ('#budget-min', '#budget-max'):
            self.assertEqual([int(option['value']) for option in admin.select(selector + ' option')], expected)

    def test_build_rejects_budgets_between_the_fixed_options(self):
        for budget in (25000, 35000, 110000, 180000, 300000, '40000.01'):
            with self.subTest(budget=budget):
                response = self.client.post('/api/build', json={'budget': budget})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error'], 'invalid_budget')

    def test_250000_option_can_recommend_a_matching_saved_system(self):
        payload = record(kind='ready', budget_min='200000', budget_max='250000',
                         parts=[{'category': 'system', 'name': 'Yüksek bütçeli test', 'price': '245000', 'url': URL}])
        self.assertEqual(self.client.post('/api/admin/systems', json=payload, headers=self.headers).status_code, 201)
        response = self.client.post('/api/build', json={'budget': 250000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 245000)
        self.assertEqual(response.json['remaining'], 5000)

    def test_end_to_end_is_offline_and_persists(self):
        with patch('requests.get', side_effect=AssertionError('Unexpected network')), patch('pc_builder.prices.AkakceSource.quotes', side_effect=AssertionError('Unexpected scraper')):
            response = self.client.post('/api/admin/systems', json=record(), headers=self.headers)
            self.assertEqual(response.status_code, 201)
            result = self.client.post('/api/build', json={'budget': 30000, 'resolution': '1080p'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['source'], 'Manuel katalog')
            self.assertLessEqual(result.json['total'], 30000)
        restarted = create_app(data_dir=self.directory.name).test_client()
        self.assertEqual(restarted.post('/api/build', json={'budget': 30000}).status_code, 200)

    def test_mutations_need_csrf_and_remote_admin_is_not_open(self):
        self.assertEqual(self.client.post('/api/admin/systems', json=record()).status_code, 403)
        self.assertEqual(self.client.get('/api/admin/systems', environ_overrides={'REMOTE_ADDR': '8.8.8.8'}).status_code, 401)
        self.assertEqual(self.client.get('/api/admin/systems', headers={'Host': 'evil.example'}).status_code, 401)
        self.assertEqual(self.app.extensions['manual_store'].list(), [])

    def test_password_login_and_logout_for_hosted_admin(self):
        app = create_app(data_dir=self.directory.name, admin_password='test-password-only')
        client = app.test_client()
        self.assertEqual(client.get('/api/admin/systems').status_code, 401)
        login = client.get('/admin').get_data(as_text=True)
        csrf = re.search(r'name="csrf" value="([^"]+)"', login).group(1)
        self.assertEqual(client.post('/admin/login', data={'csrf': csrf, 'password': 'wrong'}).status_code, 401)
        self.assertEqual(client.post('/admin/login', data={'csrf': csrf, 'password': 'test-password-only'}).status_code, 302)
        self.assertEqual(client.get('/api/admin/systems').status_code, 200)
        page = client.get('/admin').get_data(as_text=True)
        csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
        self.assertEqual(client.post('/api/admin/logout', json={}, headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(client.get('/api/admin/systems').status_code, 401)

    def test_empty_catalog_and_budget_below_total_are_not_fake_recommendations(self):
        result = self.client.post('/api/build', json={'budget': 40000})
        self.assertEqual(result.status_code, 422)
        self.assertNotIn('parts', result.json)
        self.client.post('/api/admin/systems', json=record(), headers=self.headers)
        self.assertEqual(self.client.post('/api/build', json={'budget': 20000}).status_code, 422)

    def test_update_export_import_and_delete_api(self):
        response = self.client.post('/api/admin/systems', json=record(), headers=self.headers)
        saved = response.json['system']
        payload = {**record(), 'version': saved['version'], 'name': 'Düzenlendi'}
        changed = self.client.put('/api/admin/systems/' + saved['id'], json=payload, headers=self.headers)
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.put('/api/admin/systems/' + saved['id'], json=payload, headers=self.headers).status_code, 409)
        archive = self.client.get('/api/admin/export')
        self.assertIn('attachment', archive.headers['Content-Disposition'])
        self.assertEqual(self.client.delete('/api/admin/systems/' + saved['id'], json={'version': 2}, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post('/api/admin/import', json=archive.json, headers=self.headers).status_code, 200)
        self.assertEqual(len(self.client.get('/api/admin/systems').json['systems']), 1)


if __name__ == '__main__':
    unittest.main()
