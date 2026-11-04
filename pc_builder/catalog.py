from dataclasses import dataclass, field
import re
import unicodedata


CATEGORIES = {'cpu': 'İşlemci', 'gpu': 'Ekran kartı', 'motherboard': 'Anakart', 'ram': 'Bellek', 'ssd': 'SSD', 'psu': 'Güç kaynağı', 'case': 'Kasa'}


def normalized(value):
    value = unicodedata.normalize('NFKD', value.casefold().replace('ı', 'i'))
    return re.sub(r'[^a-z0-9]', '', value)


@dataclass(frozen=True)
class Component:
    id: str
    category: str
    name: str
    query: str
    required: tuple
    quality: int
    specs: dict = field(default_factory=dict)
    excluded: tuple = ()

    def matches(self, title, sku=''):
        text = normalized(title + ' ' + sku)
        return all(normalized(term) in text for term in self.required) and not any(normalized(term) in text for term in self.excluded)


# A bounded compatibility catalog, never a price list. CPU BOX SKUs identify
# the included cooler. Unverified product variants are deliberately excluded.
CATALOG = (
    Component('r5-5500', 'cpu', 'AMD Ryzen 5 5500 · kutulu', 'AMD Ryzen 5 5500 kutulu', ('Ryzen 5 5500', '100-100000457BOX'), 50, {'socket': 'AM4', 'power': 88, 'cooler': True}, ('5500GT',)),
    Component('r5-5600', 'cpu', 'AMD Ryzen 5 5600 · kutulu', 'AMD Ryzen 5 5600 kutulu', ('Ryzen 5 5600', '100-100000927BOX'), 66, {'socket': 'AM4', 'power': 88, 'cooler': True}, ('5600X', '5600G', '5600GT')),
    Component('r5-7600', 'cpu', 'AMD Ryzen 5 7600 · kutulu', 'AMD Ryzen 5 7600 kutulu', ('Ryzen 5 7600', '100-100001015BOX'), 90, {'socket': 'AM5', 'power': 88, 'cooler': True}, ('7600X',)),
    Component('b550', 'motherboard', 'Gigabyte B550M DS3H', 'Gigabyte B550M DS3H', ('Gigabyte', 'B550M DS3H'), 50, {'socket': 'AM4', 'memory': 'DDR4', 'form': 'mATX', 'nvme': True}, ('B550MDS3HAC',)),
    Component('b650', 'motherboard', 'Gigabyte B650M D3HP', 'Gigabyte B650M D3HP', ('Gigabyte', 'B650M D3HP'), 70, {'socket': 'AM5', 'memory': 'DDR5', 'form': 'mATX', 'nvme': True}, ('AX',)),
    Component('ddr4-16', 'ram', 'Kingston Fury Beast 16 GB · 2×8 · DDR4', 'Kingston KF432C16BBK2/16', ('KF432C16BBK2/16',), 45, {'memory': 'DDR4', 'capacity': 16}),
    Component('ddr4-32', 'ram', 'Kingston Fury Beast 32 GB · 2×16 · DDR4', 'Kingston KF432C16BBK2/32', ('KF432C16BBK2/32',), 80, {'memory': 'DDR4', 'capacity': 32}),
    Component('ddr5-32', 'ram', 'Kingston Fury Beast 32 GB · 2×16 · DDR5', 'Kingston KF560C36BBEK2-32', ('KF560C36BBEK2-32',), 90, {'memory': 'DDR5', 'capacity': 32}),
    Component('rx6600', 'gpu', 'Sapphire Pulse Radeon RX 6600 · 8 GB', 'Sapphire Pulse RX 6600 8 GB', ('Sapphire', 'Pulse', 'RX 6600', '8 GB'), 38, {'length': 193, 'power': 132, 'min_psu': 500, 'pcie8': 1}, ('RX6600XT',)),
    Component('rx7600', 'gpu', 'Sapphire Pulse Radeon RX 7600 · 8 GB', 'Sapphire Pulse RX 7600 8 GB', ('Sapphire', 'Pulse', 'RX 7600', '8 GB'), 51, {'length': 240, 'power': 165, 'min_psu': 550, 'pcie8': 1}, ('RX7600XT',)),
    Component('rtx4060', 'gpu', 'MSI GeForce RTX 4060 Ventus 2X · 8 GB', 'MSI RTX 4060 Ventus 2X 8 GB', ('MSI', 'RTX 4060', 'Ventus 2X', '8 GB'), 55, {'length': 199, 'power': 115, 'min_psu': 550, 'pcie8': 1}, ('RTX4060Ti', 'White')),
    Component('rx7700xt', 'gpu', 'Sapphire Pulse Radeon RX 7700 XT · 12 GB', 'Sapphire Pulse RX 7700 XT 12 GB', ('Sapphire', 'Pulse', 'RX 7700 XT', '12 GB'), 79, {'length': 280, 'power': 245, 'min_psu': 700, 'pcie8': 2}),
    Component('rx7800xt', 'gpu', 'Sapphire Pulse Radeon RX 7800 XT · 16 GB', 'Sapphire Pulse RX 7800 XT 16 GB', ('Sapphire', 'Pulse', 'RX 7800 XT', '16 GB'), 95, {'length': 280, 'power': 263, 'min_psu': 700, 'pcie8': 2}),
    Component('sn580-1', 'ssd', 'WD Blue SN580 1 TB · NVMe', 'WD Blue SN580 WDS100T3B0E', ('WD', 'SN580', 'WDS100T3B0E'), 65, {'interface': 'NVMe', 'capacity': 1000}),
    Component('sn580-2', 'ssd', 'WD Blue SN580 2 TB · NVMe', 'WD Blue SN580 WDS200T3B0E', ('WD', 'SN580', 'WDS200T3B0E'), 90, {'interface': 'NVMe', 'capacity': 2000}),
    Component('cx650', 'psu', 'Corsair CX650 · 650 W · 80 Plus Bronze', 'Corsair CX650 CP-9020278', ('Corsair', 'CX650', 'CP-9020278'), 70, {'watts': 650, 'length': 125, 'pcie8': 2}, ('CX650M', 'CX650F')),
    Component('cx750', 'psu', 'Corsair CX750 · 750 W · 80 Plus Bronze', 'Corsair CX750 CP-9020279', ('Corsair', 'CX750', 'CP-9020279'), 75, {'watts': 750, 'length': 125, 'pcie8': 2}, ('CX750M', 'CX750F')),
    Component('matrexx40', 'case', 'DeepCool MATREXX 40', 'DeepCool MATREXX 40', ('DeepCool', 'MATREXX 40'), 50, {'forms': ['mATX', 'ITX'], 'gpu_length': 320, 'psu_length': 160}, ('3FS',)),
    Component('ap201', 'case', 'ASUS Prime AP201 · Mesh', 'Asus Prime AP201 Mesh', ('ASUS', 'AP201', 'Mesh'), 80, {'forms': ['mATX', 'ITX'], 'gpu_length': 338, 'psu_length': 180}, ('Tempered',)),
)
