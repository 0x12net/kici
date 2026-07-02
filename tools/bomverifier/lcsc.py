import json
from typing import OrderedDict

from bomverifier.api import ApiClient
from bomverifier.exceptions import MissingDataException
from bomverifier.base import BaseProvider


class LCSC(BaseProvider):
    params = {}
    url = 'https://jlcsearch.tscircuit.com/components/list.json'
    sku_column = 'lcsc'


    def __init__(self, api_client: ApiClient, item: OrderedDict, qt: int, search_type='mpn', **kwargs) -> None:
        self.api_client = api_client
        self.qt = qt
        self.item = item
        self.search_type = search_type

        self.rewrite = kwargs.get('rewrite_field')

    @property
    def required_keys(self):
        return ['lcsc_sku', 'lcsc_mpn', 'lcsc_stock', 'lcsc_price', 'lcsc_consistent', 'lcsc_enough']

    def validate(self):
        self.search_by = self._get_search_by(self.search_type)

    def update_with_data(self):
        self.params.update({'search': self.search_by})
        data = self.api_client.send_request(self.url, self.params)
        
        rows = data['components']
        if rows:
            row = rows[0]

            sku = 'C'+ str(row.get('lcsc'))
            mpn = row.get('mfr')
            stock = row.get('stock')
            price = self._get_price(row.get('price'))
            consistent = bool((self.item.get('lcsc')==sku) and (self.item.get('mpn') == mpn))
            enough = bool(self.qt <= int(stock))

            data = [sku, mpn, stock, price, consistent, enough]
            self._update(data)
            self._rewrite(sku, mpn)

        else:
            self.fill_with_empty_values()

    def _get_price(self, price):
        if not price:
            return None
        for tier in json.loads(price):
            q_to = tier.get('qTo')
            if tier['qFrom'] <= self.qt and (q_to is None or self.qt <= q_to):
                return float(tier['price'])
        return None

    def _get_search_by(self, search_type):
        search_by = None
        if search_type == 'mpn':
            search_by = self.item.get('mpn').strip()
        elif search_type == 'sku':
            search_by = self.item.get('lcsc').strip()[1:]
        if search_by:
            return search_by
        raise MissingDataException

