from typing import OrderedDict

import digikey
from digikey.exceptions import DigikeyError
from digikey.v3.productinformation import KeywordSearchRequest

from bomverifier.api import ApiClient
from bomverifier.exceptions import MissingDataException, ApiException
from bomverifier.base import BaseProvider


class DigiKey(BaseProvider):
    sku_column = 'digikey'

    def __init__(self, api_client: ApiClient, item: OrderedDict, qt: int, search_type='mpn', **kwargs) -> None:
        self.qt = qt
        self.item = item
        self.search_type = search_type

        self.rewrite = kwargs.get('rewrite_field')

    @property
    def required_keys(self):
        return ['digikey_sku', 'digikey_mpn', 'digikey_stock', 'digikey_price', 'digikey_consistent', 'digikey_enough']

    def validate(self):
        self.search_by = self._get_search_by(self.search_type)

    def update_with_data(self):
        try:
            if self.search_type == 'sku':
                part = digikey.product_details(self.search_by)
            else:
                result = digikey.keyword_search(body=KeywordSearchRequest(keywords=self.search_by, record_count=1))
                part = result.products[0] if result and result.products else None
        except DigikeyError as e:
            print(f'\033[31mERROR\033[0m: API {e}')
            raise ApiException

        if part:
            sku = part.digi_key_part_number
            mpn = part.manufacturer_part_number
            stock = part.quantity_available
            price = self._get_price(part.standard_pricing)
            consistent = bool((self.item.get('digikey') == sku) and (self.item.get('mpn') == mpn))
            enough = bool(self.qt <= int(stock))

            data = [sku, mpn, stock, price, consistent, enough]
            self._update(data)
            self._rewrite(sku, mpn)
        else:
            self.fill_with_empty_values()

    def _get_price(self, price_breaks):
        if not price_breaks:
            return None
        selected = None
        for tier in sorted(price_breaks, key=lambda p: p.break_quantity):
            if tier.break_quantity <= self.qt:
                selected = tier.unit_price
        return selected

    def _get_search_by(self, search_type):
        search_by = None
        if search_type == 'mpn':
            search_by = self.item.get('mpn')
        elif search_type == 'sku':
            search_by = self.item.get('digikey')
        if search_by:
            return search_by.strip()
        raise MissingDataException
