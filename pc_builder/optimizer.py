from datetime import datetime, timezone
from decimal import Decimal
from itertools import product

from .catalog import CATEGORIES


def compatibility(parts):
    cpu, gpu, board, ram, ssd, psu, case = (parts[key] for key in CATEGORIES)
    return (
        cpu.specs['socket'] == board.specs['socket']
        and ram.specs['memory'] == board.specs['memory']
        and board.specs['form'] in case.specs['forms']
        and gpu.specs['length'] <= case.specs['gpu_length']
        and psu.specs['length'] <= case.specs['psu_length']
        and psu.specs['watts'] >= gpu.specs['min_psu']
        and psu.specs['watts'] * 4 >= (cpu.specs['power'] + gpu.specs['power'] + 100) * 5
        and psu.specs['pcie8'] >= gpu.specs['pcie8']
        and cpu.specs['cooler'] and board.specs['nvme']
        and ssd.specs['interface'] == 'NVMe'
    )


def choose_build(catalog, quotes, budget, resolution='1080p'):
    budget = Decimal(str(budget))
    available = {category: [part for part in catalog if part.category == category and part.id in quotes] for category in CATEGORIES}
    if any(not options for options in available.values()):
        return None
    gpu_weight = {'1080p': 45, '1440p': 53, '4k': 60}[resolution]
    weights = {'cpu': 70 - gpu_weight, 'gpu': gpu_weight, 'motherboard': 3, 'ram': 8, 'ssd': 7, 'psu': 4, 'case': 3}
    best, best_key = None, None
    for selection in product(*available.values()):
        parts = dict(zip(CATEGORIES, selection))
        if not compatibility(parts):
            continue
        total = sum((quotes[part.id].price for part in selection), Decimal('0'))
        if total > budget:
            continue
        score = sum(weights[part.category] * part.quality for part in selection)
        key = (score, -total)
        if best_key is None or key > best_key:
            best, best_key = (parts, total), key
    if best is None:
        return None
    parts, total = best
    warnings = [
        'Fiyatlar ve stoklar satın alma sırasında değişebilir. Kargo, montaj, işletim sistemi ve çevre birimleri toplama dahil değildir.',
        'Siparişten önce satıcıdaki ürün kodunu, anakart BIOS sürümünü ve kutu içeriğini doğrula. XMP / EXPO bellek hızları BIOS ayarı gerektirebilir.',
        'Öneri sınırlı parça kataloğumuzdaki seçenekler arasındadır; tüm piyasanın en iyi sistemi veya FPS garantisi değildir.',
    ]
    if resolution == '4k' and parts['gpu'].quality < 90:
        warnings.append('Bu bütçedeki ekran kartı 4K oyunlarda ayar veya çözünürlük düşürmeyi gerektirebilir.')
    return {
        'budget': float(budget), 'total': float(total), 'remaining': float(budget - total),
        'resolution': resolution, 'source': 'Akakçe',
        'oldest_price_check': min(quotes[part.id].checked_at for part in parts.values()),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'parts': [{'id': part.id, 'category': part.category, 'category_name': CATEGORIES[part.category],
                   'name': part.name, 'listing_name': quotes[part.id].title,
                   'price': float(quotes[part.id].price), 'url': quotes[part.id].url,
                   'checked_at': quotes[part.id].checked_at} for part in parts.values()],
        'checks': [f"{parts['cpu'].specs['socket']} işlemci ve anakart eşleşmesi",
                   f"{parts['ram'].specs['memory']} bellek uyumu",
                   'Ekran kartı ve güç kaynağı boyutları kasaya uygun',
                   f"{parts['psu'].specs['watts']} W güç kaynağı ve PCIe bağlantıları yeterli",
                   'Kutulu işlemcinin soğutucusu dahil'],
        'warnings': warnings,
    }
