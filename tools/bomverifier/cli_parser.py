import sys
import argparse
import os


class OptionsParser():
    PROVIDERS_LIST = ['lcsc', 'digikey']

    def __init__(self, options) -> None:
        self.options = options
        self._validate()

    def get_run_options(self):
        providers_by_name = {}

        for name, value in self.options.items():
            if name in self.PROVIDERS_LIST and value:
                provider = {'name': name, 'search_type': value, 'options': {}}
                providers_by_name[name] = provider

                rewrite_field = self.options.get(f'{name}RW')
                if rewrite_field:
                    provider['options']['rewrite_field'] = rewrite_field

        # Providers are processed in the order their flags appear on the command
        # line, so that data written by one provider (e.g. mpn) can be used in the
        # search of the next one.
        order = self.options.get('_provider_order') or []
        providers_to_search = [providers_by_name[n] for n in order if n in providers_by_name]
        for name, provider in providers_by_name.items():
            if provider not in providers_to_search:
                providers_to_search.append(provider)

        input_file = self.options.get('input')
        output_file = self.options.get('output')
        qty = self.options.get('qty')

        return {
            'providers': providers_to_search,
            'input_file': input_file,
            'output_file': output_file,
            'qty': qty
        }

    def _validate(self):
        # print('Validating arguments')
        if not self.options.get('output'):
            print('CRITICAL: output path is a required argument')
            sys.exit(2)
        if self.options.get('lcscRW') and self.options.get('lcsc'):
            if self.options['lcscRW'] == self.options['lcsc']:
                print('CRITICAL: lcsc and lcscRW must not match')
                sys.exit(2)
        if self.options.get('digikeyRW') and self.options.get('digikey'):
            if self.options['digikeyRW'] == self.options['digikey']:
                print('CRITICAL: digikey and digikeyRW must not match')
                sys.exit(2)
        if self.options.get('qty') <= 0:
            print('CRITICAL: qty < 0')
            sys.exit(2)
        if not os.path.isfile(self.options['input']):
            print(f"CRITICAL: file '{self.options['input']}' not found!")
            sys.exit(1)
        # print('All good')



def parse_argumetns():
    parser = argparse.ArgumentParser()

    parser.add_argument('input', type=str, help='bom file')
    parser.add_argument('-o', dest='output', type=str, help='path to output file')
    parser.add_argument('-lcsc', choices=['sku', 'mpn'], type=str, help='search data from distributor')
    parser.add_argument('-lcscRW', choices=['sku', 'mpn'], type=str, help='rewrite cells according to distributor data')
    parser.add_argument('-digikey', choices=['sku', 'mpn'], type=str, help='search data from distributor')
    parser.add_argument('-digikeyRW', choices=['sku', 'mpn'], type=str, help='rewrite cells according to distributor data')
    parser.add_argument('-qty', default=1, type=int, help='number of items in the order')

    args = parser.parse_args()
    args = vars(args)
    args['_provider_order'] = _provider_order(sys.argv[1:])
    return args


def _provider_order(argv):
    """Order of first appearance of provider flags (-lcsc, -digikey ...) in argv."""
    order = []
    for token in argv:
        for name in OptionsParser.PROVIDERS_LIST:
            flag = '-' + name
            if token == flag or token.startswith(flag + '='):
                if name not in order:
                    order.append(name)
    return order












