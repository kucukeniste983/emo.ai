"""Owner-curated builds. Reading this catalog never contacts price websites."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from .catalog import CATEGORIES
from .prices import safe_url

MANUAL_CATEGORIES = {**CATEGORIES, 'cooler': 'İşlemci soğutucu'}
MIN_BUDGET, MAX_BUDGET = 1000, 500000


class ManualError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def default_data_dir():
    configured = os.environ.get('RIGLAB_DATA_DIR')
    if configured:
        return Path(configured)
    if os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'riglab'
    return Path(__file__).resolve().parents[1] / 'data'


def amount(value, label, *, minimum=0, maximum=MAX_BUDGET):
    try:
        if isinstance(value, bool):
            raise ValueError
        number = Decimal(str(value))
        if not number.is_finite() or not minimum <= number <= maximum or number.as_tuple().exponent < -2:
            raise ValueError
        return number.quantize(Decimal('0.01'))
    except (ValueError, TypeError, InvalidOperation):
        raise ManualError(f'{label}: geçerli bir TL tutarı gir.') from None


def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ManualError(f'{label} alanını kontrol et (en fazla {limit} karakter).')
    return value.strip()


def normalize(payload):
    if not isinstance(payload, dict):
        raise ManualError('Sistem bilgileri geçerli bir JSON nesnesi olmalı.')
    name = text(payload.get('name', ''), 'Sistem adı', 120, True)
    low = amount(payload.get('budget_min'), 'Alt bütçe', minimum=MIN_BUDGET)
    high = amount(payload.get('budget_max'), 'Üst bütçe', minimum=MIN_BUDGET)
    if low > high:
        raise ManualError('Alt bütçe, üst bütçeden büyük olamaz.')
    resolution = payload.get('resolution', 'any')
    if resolution not in ('any', '1080p', '1440p', '4k'):
        raise ManualError('Geçerli bir çözünürlük seç.')
    kind = payload.get('kind', 'parts')
    if kind not in ('parts', 'ready'):
        raise ManualError('Sistem türü parça listesi veya hazır sistem olmalı.')
    priority = payload.get('priority', 50)
    if type(priority) is not int or not 0 <= priority <= 100:
        raise ManualError('Öneri önceliği 0–100 arasında tam sayı olmalı.')
    enabled = payload.get('enabled', False)
    confirmed = payload.get('compatibility_confirmed', False)
    if type(enabled) is not bool or type(confirmed) is not bool:
        raise ManualError('Yayın ve kontrol durumları geçersiz.')
    rows = payload.get('parts', [])
    if not isinstance(rows, list) or len(rows) > 8:
        raise ManualError('En fazla sekiz parça ekleyebilirsin.')
    allowed = {'system': 'Hazır sistem'} if kind == 'ready' else MANUAL_CATEGORIES
    parts, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get('category') not in allowed:
            raise ManualError('Parça kategorisi geçersiz.')
        category = row['category']
        if category in seen:
            raise ManualError('Aynı parça kategorisi birden fazla kez eklenemez.')
        seen.add(category)
        part_name = text(row.get('name', ''), allowed[category], 180)
        url = text(row.get('url', ''), 'İlan bağlantısı', 2048)
        if url and not safe_url(url, product_only=True):
            raise ManualError(f'{allowed[category]}: HTTPS ile başlayan bir Akakçe ürün bağlantısı gir.')
        value = row.get('price')
        price = None if value is None or value == '' else amount(value, allowed[category] + ' fiyatı')
        if not part_name and not url and price is None:
            continue
        parts.append({'category': category, 'name': part_name, 'price': str(price) if price is not None else None, 'url': url})
    total = sum((Decimal(row['price']) for row in parts if row['price'] is not None), Decimal('0'))
    if enabled:
        required = {'system'} if kind == 'ready' else set(CATEGORIES)
        complete = {row['category'] for row in parts if row['name'] and row['url'] and row['price'] is not None}
        if not required.issubset(complete) or len(complete) != len(parts):
            raise ManualError('Yayınlamak için tüm gerekli ad, fiyat ve bağlantıları tamamla. Yarım kaydı taslak olarak saklayabilirsin.')
        if not confirmed:
            raise ManualError('Yayınlamadan önce ilanları ve donanım uyumluluğunu kontrol ettiğini onayla.')
        if total <= 0 or total > high:
            raise ManualError('Sistem toplamı pozitif olmalı ve üst bütçeyi aşmamalı.')
    return {'name': name, 'budget_min': str(low), 'budget_max': str(high), 'resolution': resolution,
            'kind': kind, 'priority': priority, 'enabled': enabled, 'compatibility_confirmed': confirmed,
            'notes': text(payload.get('notes', ''), 'Notlar', 2000), 'parts': parts, 'total': str(total)}


class ManualStore:
    mode = 'manual'

    def __init__(self, data_dir=None):
        self.path = Path(data_dir if data_dir is not None else default_data_dir()) / 'manual.sqlite3'

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(self.path, timeout=10)
        try:
            database.execute('CREATE TABLE IF NOT EXISTS systems (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)')
            yield database
        finally:
            database.close()

    def list(self):
        with self.connection() as database:
            values = [json.loads(row[0]) for row in database.execute('SELECT payload FROM systems')]
        return sorted(values, key=lambda row: row['updated_at'], reverse=True)

    def save(self, payload, system_id=None, version=None):
        record = normalize(payload)
        with self.connection() as database, database:
            if system_id is not None:
                existing = database.execute('SELECT version FROM systems WHERE id=?', (system_id,)).fetchone()
                if existing is None:
                    raise ManualError('Sistem bulunamadı.', 404)
                if type(version) is not int or existing[0] != version:
                    raise ManualError('Bu kayıt başka bir pencerede değişti. Listeyi yenileyip tekrar düzenle.', 409)
            record.update(id=system_id or uuid4().hex, version=(version + 1 if system_id else 1),
                          updated_at=datetime.now(timezone.utc).isoformat())
            serialized = json.dumps(record, ensure_ascii=False)
            if system_id:
                changed = database.execute('UPDATE systems SET version=?, payload=? WHERE id=? AND version=?',
                                           (record['version'], serialized, system_id, version)).rowcount
                if changed != 1:
                    raise ManualError('Kayıt değişti; listeyi yenile.', 409)
            else:
                database.execute('INSERT INTO systems VALUES (?,?,?)', (record['id'], record['version'], serialized))
        return record

    def delete(self, system_id, version):
        if type(version) is not int:
            raise ManualError('Kayıt sürümü gerekli.')
        with self.connection() as database, database:
            changed = database.execute('DELETE FROM systems WHERE id=? AND version=?', (system_id, version)).rowcount
            if changed != 1:
                raise ManualError('Kayıt değişti veya silindi. Listeyi yenile.', 409)

    def export(self):
        return {'schema_version': 1, 'systems': self.list()}

    def restore(self, payload):
        if not isinstance(payload, dict) or payload.get('schema_version') != 1:
            raise ManualError('Geçerli bir RIGLAB yedeği seç.')
        rows = payload.get('systems')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
            raise ManualError('Yedek 1–200 sistem içermeli.')
        records, ids = [], set()
        for item in rows:
            record = normalize(item)
            system_id = item.get('id', uuid4().hex)
            if not isinstance(system_id, str) or not re.fullmatch('[0-9a-f]{32}', system_id) or system_id in ids:
                raise ManualError('Yedekte geçersiz veya yinelenen sistem kimliği var.')
            ids.add(system_id)
            record['id'] = system_id
            records.append(record)
        with self.connection() as database, database:
            for record in records:
                old = database.execute('SELECT version FROM systems WHERE id=?', (record['id'],)).fetchone()
                record.update(version=(old[0] + 1 if old else 1), updated_at=datetime.now(timezone.utc).isoformat())
                database.execute('INSERT OR REPLACE INTO systems VALUES (?,?,?)',
                                 (record['id'], record['version'], json.dumps(record, ensure_ascii=False)))
        return len(records)

    def recommend(self, budget, resolution):
        eligible = [row for row in self.list() if row['enabled'] and Decimal(row['budget_min']) <= budget <= Decimal(row['budget_max'])
                    and Decimal(row['total']) <= budget and row['resolution'] in ('any', resolution)]
        if not eligible:
            return None
        row = max(eligible, key=lambda item: (item['priority'], Decimal(item['budget_min']), Decimal(item['total']), item['id']))
        total = Decimal(row['total'])
        labels = {'system': 'Hazır sistem', **MANUAL_CATEGORIES}
        order = list(labels)
        return {'id': row['id'], 'system_name': row['name'], 'mode': 'manual', 'source': 'Manuel katalog',
                'budget': float(budget), 'total': float(total), 'remaining': float(budget - total), 'resolution': resolution,
                'oldest_price_check': row['updated_at'], 'generated_at': datetime.now(timezone.utc).isoformat(),
                'parts': [{'id': row['id'] + '-' + part['category'], 'category': part['category'], 'category_name': labels[part['category']],
                           'name': part['name'], 'listing_name': part['name'], 'price': float(Decimal(part['price'])),
                           'url': part['url'], 'checked_at': row['updated_at']}
                          for part in sorted(row['parts'], key=lambda part: order.index(part['category']))],
                'checks': ['Toplam tutar bütçeni aşmıyor.', 'Bağlantılar ve uyumluluk kaydı hazırlayan tarafından kontrol edildi.'],
                'warnings': ['Fiyatlar elle girildi; Akakçe’den otomatik doğrulanmadı. Son fiyatı ve stoğu ilan sayfasında kontrol et.',
                             'Kargo, montaj, işletim sistemi ve çevre birimleri dahil değildir.',
                             'Donanım uyumluluğu bu manuel listede otomatik ölçülmez; ürün kodlarını ve kutu içeriğini satın almadan önce kontrol et.'] + ([row['notes']] if row['notes'] else [])}
