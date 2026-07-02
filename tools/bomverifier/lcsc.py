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
        tiers = json.loads(price)
        if not tiers:
            return None
        # Pick the highest-quantity break whose qFrom is still <= qty_total.
        selected = None
        for tier in sorted(tiers, key=lambda t: t['qFrom']):
            if tier['qFrom'] <= self.qt:
                selected = tier
        # qty_total is below the smallest break (LCSC MOQ): fall back to that
        # break so a price is still reported instead of an empty cell.
        if selected is None:
            selected = min(tiers, key=lambda t: t['qFrom'])
        return float(selected['price'])

    def _get_search_by(self, search_type):
        search_by = None
        if search_type == 'mpn':
            search_by = self.item.get('mpn').strip()
        elif search_type == 'sku':
            search_by = self.item.get('lcsc').strip()[1:]
        if search_by:
            return search_by
        raise MissingDataException

