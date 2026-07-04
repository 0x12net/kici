from bomverifier.api import ApiClient
from bomverifier.cli_parser import parse_arguments, OptionsParser
from bomverifier.csv_parser import read_csv_rows, update_row_with_providers, write_rows, verify_providers_auth
from bomverifier.exceptions import MissingDataException

arguments = parse_arguments()
run_options = OptionsParser(arguments).get_run_options()

# Check credentials once, up front, so a provider with no working credentials
# is skipped for the whole run instead of failing auth on every BOM row.
run_options['providers'] = verify_providers_auth(run_options['providers'])

api_client = ApiClient()
updated_rows = []

for number, row in enumerate(read_csv_rows(run_options['input_file']), start=1):
    try:
        update_row_with_providers(row, run_options['qty'], run_options['providers'], number, api_client)
    except MissingDataException as e:
        print(f'\033[31mERROR\033[0m: Data error {e}')
    updated_rows.append(row)

write_rows(run_options['output_file'], updated_rows)
