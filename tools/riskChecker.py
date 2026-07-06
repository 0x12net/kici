import csv
import sys
import re
import argparse
from collections import OrderedDict

# Risk classification csv columns: risk_level,part,description
#   risk_level  1 (low) / 2 (medium) / 3 (critical)
#   part        chip name or MPN/SKU, glob pattern ('*'/'?' wildcards, case-insensitive)
#   description free text, printed in the report
REQUIRED_CSV_COLUMNS = ('risk_level', 'part')
HIT_FIELDS = ('designator', 'comment', 'mpn', 'field', 'level', 'matched_part', 'description')

LEVEL_LABEL = {1: '\033[32mLOW\033[0m', 2: '\033[33mMEDIUM\033[0m', 3: '\033[31mCRITICAL\033[0m'}

parser = argparse.ArgumentParser(description='Check BOM parts against a risk classification table')
parser.add_argument('bom_file', help='BOM csv exported by kicad-cli (columns: designator, comment, mpn, ...)')
parser.add_argument('classification_file', help='Risk classification csv (columns: risk_level,part,description)')
parser.add_argument('-o', '--output', help='Write every match found to this csv')
parser.add_argument('--fail-level', type=int, default=3, help='Exit non-zero if any part reaches this risk level (default: 3)')
args = parser.parse_args()


def glob_to_regex(pattern):
    "Same human-glob convention as cplCorrector.py: '*'/'?' are wildcards, everything else is literal"
    escaped = ''.join(re.escape(char) if char not in ('*', '?') else char for char in pattern)
    escaped = escaped.replace('*', '.*').replace('?', '.')
    return re.compile(f'^{escaped}$', re.IGNORECASE)


def read_header(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        return [title.strip().lower() for title in next(csv.reader(csvfile))]


def read_rows(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = [title.strip().lower() for title in next(reader)]
        for row in reader:
            yield OrderedDict(zip(header, row))


def load_rules(filename):
    missing_columns = set(REQUIRED_CSV_COLUMNS) - set(read_header(filename))
    if missing_columns:
        print(f"CRITICAL: classification file is missing columns: {', '.join(sorted(missing_columns))}")
        sys.exit(2)

    rules = []
    for row_number, row in enumerate(read_rows(filename), start=2):
        try:
            level = int(row['risk_level'])
        except ValueError:
            print(f'\033[33mWARN\033[0m: skip classification row {row_number}: invalid risk_level {row["risk_level"]!r}')
            continue
        part = row['part'].strip()
        if not part:
            print(f'\033[33mWARN\033[0m: skip classification row {row_number}: empty part')
            continue
        rules.append({'level': level, 'pattern': glob_to_regex(part), 'part': part, 'description': row.get('description', '')})
    return rules


def identifiers(bom_row):
    "Every non-empty BOM column: chip/value name, mpn, distributor sku, or any other field a part list may use"
    return {name: value for name, value in bom_row.items() if value}


def find_matches(bom_row, rules):
    "Classification rules matching this BOM part, one hit per rule (not per matched field)"
    row_identifiers = identifiers(bom_row)
    matches = []
    for rule in rules:
        matched_fields = [field for field, value in row_identifiers.items() if rule['pattern'].match(value)]
        if matched_fields:
            matches.append({
                'designator': bom_row.get('designator', ''),
                'comment': bom_row.get('comment', ''),
                'mpn': bom_row.get('mpn', ''),
                'field': ','.join(matched_fields),
                'level': rule['level'],
                'matched_part': rule['part'],
                'description': rule['description'],
            })
    return matches


def print_report(hits):
    for hit in hits:
        label = LEVEL_LABEL.get(hit['level'], str(hit['level']))
        print(f"[{label}] {hit['comment']} ({hit['designator']})")
        print(f"    mpn:         {hit['mpn']}")
        print(f"    matched:     {hit['field']}=\"{hit['matched_part']}\"")
        print(f"    description: {hit['description']}")
        print()


def write_hits_csv(filename, hits):
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, HIT_FIELDS, dialect=csv.unix_dialect)
        writer.writeheader()
        writer.writerows(hits)


rules = load_rules(args.classification_file)

hits = []
for bom_row in read_rows(args.bom_file):
    hits.extend(find_matches(bom_row, rules))
hits.sort(key=lambda hit: -hit['level'])
max_level = max((hit['level'] for hit in hits), default=0)

print_report(hits)

if args.output:
    write_hits_csv(args.output, hits)

if not hits:
    print('INFO: No parts matched the risk classification table')
else:
    print(f'INFO: Highest risk level found: {max_level} ({LEVEL_LABEL.get(max_level, max_level)})')

sys.exit(1 if max_level >= args.fail_level else 0)
