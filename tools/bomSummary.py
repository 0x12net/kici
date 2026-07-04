import argparse
import csv
import re
import sys

PRICE_COLUMN_RE = re.compile(r'^(.+)_price$')

DISPLAY_NAMES = {
    'lcsc': 'LCSC',
    'digikey': 'DigiKey',
    'chipdip': 'ChipDip',
    'promelec': 'Promelec',
}

parser = argparse.ArgumentParser(
    description='Per-provider cost / missing-parts summary across one or more bom_stock CSVs '
                '(e.g. all boards in one manufacturing batch)')
parser.add_argument('inputs', nargs='+', help='bom_stock.csv file(s)')
args = parser.parse_args()

totals = {}


def get_totals(provider):
    return totals.setdefault(provider, {'cost': 0.0, 'lines': 0, 'missing_lines': 0, 'missing_qty': 0})


def get_providers(fieldnames):
    providers = []
    for column in fieldnames or []:
        match = PRICE_COLUMN_RE.match(column)
        if match:
            providers.append(match.group(1))
    return providers


for path in args.inputs:
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        providers = get_providers(reader.fieldnames)

        for row in reader:
            try:
                qty_total = int(row.get('qty_total') or 0)
            except ValueError:
                qty_total = 0

            for provider in providers:
                stats = get_totals(provider)
                stats['lines'] += 1

                price = row.get(f'{provider}_price')
                if price:
                    stats['cost'] += float(price) * qty_total

                if row.get(f'{provider}_enough') != 'True':
                    stats['missing_lines'] += 1
                    stats['missing_qty'] += qty_total

def sort_key(provider):
    # fully-stocked suppliers first, cheapest of those first; partial suppliers after, cheapest first
    stats = totals[provider]
    return (stats['missing_lines'] > 0, stats['cost'])


writer = csv.writer(sys.stdout, dialect=csv.unix_dialect)
writer.writerow(['provider', 'cost', 'lines_covered', 'missing_qty', 'covers_full_batch'])
for provider in sorted(totals, key=sort_key):
    stats = totals[provider]
    covered_lines = stats['lines'] - stats['missing_lines']
    writer.writerow([
        DISPLAY_NAMES.get(provider, provider),
        f'${stats["cost"]:.2f}',
        f'{covered_lines}/{stats["lines"]}',
        stats['missing_qty'],
        stats['missing_lines'] == 0,
    ])
