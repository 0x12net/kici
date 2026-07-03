import csv
from collections import OrderedDict

from bomverifier.lcsc import LCSC
from bomverifier.digikey import DigiKey
from bomverifier.api import ApiClient
from bomverifier.exceptions import MissingDataException, ArgsException, ApiException


PROVIDER_CLASSES = {
    'lcsc': LCSC,
    'digikey': DigiKey
}


def read_csv_rows(filename):
    print(f'Read {filename}')
    with open(filename, newline='', encoding='utf-8') as csvfile:
        rows = csv.reader(csvfile)
        header = next(rows)
        header = [title.lower() for title in header]
        
        for row in rows:
            yield OrderedDict(zip(header, row))


def update_row_with_providers(row, qty, providers, row_number, api_client):
    try:
        qty_total = qty * int(row['qty'])
    except ValueError:
        raise MissingDataException('\033[31mERROR\033[0m: Invalid `qty` value')

    row['qty_total'] = qty_total

    for provider in providers:
        print(f'INFO: ({row_number}) [{provider["name"]}]\tmpn:{row["mpn"]}\t\tcomment:{row["comment"]}')
        provider_class = PROVIDER_CLASSES.get(provider['name'])
        try:
            row_provider = provider_class(api_client, row, qty_total, search_type=provider['search_type'], **provider['options'])
            row_provider.validate()
            row_provider.update_with_data()
        except MissingDataException:
            print(f'\033[33mWARN\033[0m: ({row_number}) [{provider["name"]}]\tComponent not found')
            row_provider.fill_with_empty_values()
        except ArgsException as e:
            print(f'\033[31mERROR\033[0m: ({row_number}) [{provider["name"]}]\tInvalid argument: {e}')
        except ApiException as e:
            row_provider.fill_with_empty_values()
            print(f'\033[31mERROR\033[0m: ({row_number}) [{provider["name"]}]\tAPI is broken: {e}')


def write_rows(output_file, rows):
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        if not rows:
            print('\033[33mWARN\033[0m: No data to record')
            return
        writer = csv.DictWriter(csvfile, rows[0].keys(), delimiter=',', dialect=csv.unix_dialect)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        print(f'INFO: Number of lines written: {len(rows)}')