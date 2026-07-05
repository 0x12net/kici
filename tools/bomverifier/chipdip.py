import json
import re
from os import getenv
from typing import OrderedDict

import requests

from bomverifier.api import DEFAULT_USER_AGENT, get_proxies
from bomverifier.base import BaseProvider
from bomverifier.currency import rub_to_usd
from bomverifier.exceptions import ApiException, MissingDataException


# No partner API for third-party sku/price lookup — scrapes the public search page
# instead; searching by the internal id works there too.


class ChipDip(BaseProvider):
    url = 'https://www.chipdip.ru/search'
    sku_column = 'chipdip'

    _ROW_RE = re.compile(r'<tr class="with-hover" id="item(\d+)">(.*?)</tr>', re.S)
    _NAME_RE = re.compile(r'<b>([^<]*)</b>')
    _HREF_RE = re.compile(r'<a class="link" href="([^"]+)"')
    _MODEL_RE = re.compile(r'itemprop="model">([^<]*)<')
    _DISCOUNTS_RE = re.compile(r'data-discounts="(\[[^"]*\])"')
    _QTY_RE = re.compile(r'([\d\s\xa0]+)шт\.')

    def __init__(self, api_client, item: OrderedDict, qt: int, search_type='mpn', **kwargs) -> None:
        self.qt = qt
        self.item = item
        self.search_type = search_type
        self.rewrite = kwargs.get('rewrite_field')

    @property
    def required_keys(self):
        return ['chipdip_sku', 'chipdip_mpn', 'chipdip_stock', 'chipdip_price', 'chipdip_consistent', 'chipdip_enough']

    def validate(self):
        self.search_by = self._get_search_by(self.search_type)

    def update_with_data(self):
        html = self._request()
        row = self._ROW_RE.search(html)
        if not row:
            raise MissingDataException

        sku = row.group(1)
        body = row.group(2)

        # An exact-id hit has no <b> highlight, unlike a free-text match — fetch the mpn from the product page instead.
        name_match = self._NAME_RE.search(body)
        mpn = name_match.group(1).strip() if name_match else self._fetch_mpn(body)
        stock = self._get_stock(body)
        price = self._get_price(body)

        consistent = bool((self.item.get('chipdip') == sku) and (self.item.get('mpn') == mpn))
        enough = bool(stock is not None and self.qt <= stock)

        data = [sku, mpn, stock, price, consistent, enough]
        self._update(data)
        self._rewrite(sku, mpn)

    def _request(self):
        # No blanket raise_for_status(): a genuine "nothing found" answers with
        # HTTP 404 but a normal, parseable page. Any other non-2xx status
        # (anti-bot block, 5xx, ...) is a real failure, not "not found" -- flag
        # it as such instead of silently falling through to an empty result.
        headers = {'User-Agent': getenv('USERAGENT', DEFAULT_USER_AGENT)}
        try:
            response = requests.get(
                self.url, params={'searchtext': self.search_by},
                headers=headers, proxies=get_proxies(), timeout=30,
            )
        except requests.RequestException as e:
            raise ApiException(str(e)) from e
        if response.status_code >= 400 and response.status_code != 404:
            raise ApiException(f'unexpected status {response.status_code}')
        return response.text

    def _fetch_mpn(self, body):
        href = self._HREF_RE.search(body)
        if not href:
            return None
        headers = {'User-Agent': getenv('USERAGENT', DEFAULT_USER_AGENT)}
        try:
            response = requests.get(
                f'https://www.chipdip.ru{href.group(1)}',
                headers=headers, proxies=get_proxies(), timeout=30,
            )
        except requests.RequestException:
            return None
        model = self._MODEL_RE.search(response.text)
        return model.group(1).strip() if model else None

    def _get_stock(self, body):
        m = self._QTY_RE.search(body)
        if not m:
            return None
        digits = m.group(1).replace('\xa0', '').replace(' ', '').strip()
        return int(digits) if digits else None

    def _get_price(self, body):
        m = self._DISCOUNTS_RE.search(body)
        if not m:
            return None
        tiers = json.loads(m.group(1))
        if not tiers:
            return None
        # Pick the highest-quantity break whose qFrom is still <= qty_total.
        selected = None
        for qty_from, tier_price in sorted(tiers, key=lambda t: t[0]):
            if qty_from <= self.qt:
                selected = tier_price
        # qty_total is below the smallest break: fall back to that break so a
        # price is still reported instead of an empty cell.
        if selected is None:
            selected = min(tiers, key=lambda t: t[0])[1]
        return rub_to_usd(float(selected))

    def _get_search_by(self, search_type):
        search_by = None
        if search_type == 'mpn':
            search_by = self.item.get('mpn').strip()
        elif search_type == 'sku':
            search_by = self.item.get('chipdip').strip()
        if search_by:
            return search_by
        raise MissingDataException
