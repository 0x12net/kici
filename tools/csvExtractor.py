import csv
import sys
import argparse

parser = argparse.ArgumentParser(description='CSV file extractor')
parser.add_argument('input', help='Input file [*.csv]')
parser.add_argument('columns', help='Name of columns to be extracted ["qty,mpn,..."]')
parser.add_argument('-o', '--output', help='Output file name')
args = parser.parse_args()

columns = args.columns.split(',')

with open(args.input, 'r', encoding='utf-8') as input_file:
    reader = csv.DictReader(input_file)
    rows = [[row.get(column, '') for column in columns] for row in reader]


def write_rows(stream):
    writer = csv.writer(stream, dialect=csv.unix_dialect)
    writer.writerow(columns)
    writer.writerows(rows)


if args.output is None:
    write_rows(sys.stdout)
else:
    with open(args.output, 'w', newline='', encoding='utf-8') as output_file:
        write_rows(output_file)
