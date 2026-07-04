import http.client
import json
from os import getenv
from typing import OrderedDict

import requests

from bomverifier.api import DEFAULT_USER_AGENT, get_proxies
from bomverifier.base import BaseProvider
from bomverifier.currency import rub_to_usd
from bomverifier.exceptions import ApiException, MissingDataException


# No documented public API — drives the undocumented PROM2PROM (office.promelec.ru)
# search JSON endpoint instead. Requires a partner account: PROMELEC_LOGIN / PROMELEC_PASSWORD.

# The login response carries ~85+ Set-Cookie headers, which trips Python's default header-count limit.
http.client._MAXHEADERS = 1000

_LOGIN_URL = 'https://office.promelec.ru/'
_SEARCH_URL = 'https://office.promelec.ru/php/ajax-search-fast.php'

# Cached at module scope so login runs once per process, not once per BOM row (cf. the DigiKey token cache).
_session = {'value': None}


def _get_session():
    if _session['value'] is not None:
        return _session['value']

    login = getenv('PROMELEC_LOGIN')
    password = getenv('PROMELEC_PASSWORD')
    if not login or not password:
        print('\033[31mERROR\033[0m: PROMELEC_LOGIN / PROMELEC_PASSWORD are not set')
        raise ApiException

    session = requests.Session()
    session.headers.update({'User-Agent': getenv('USERAGENT', DEFAULT_USER_AGENT)})
    session.proxies = get_proxies() or {}

    try:
        response = session.post(_LOGIN_URL, data={
            'login_reg': login,
            'password_reg': password,
            'remember_me': 'on',
            'autorize': 'form_login',
            'url': '/',
        }, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'\033[31mERROR\033[0m: promelec auth {e}')
        raise ApiException

    if 'login_reg' in response.text:
        print('\033[31mERROR\033[0m: promelec auth failed (invalid PROMELEC_LOGIN/PROMELEC_PASSWORD?)')
        raise ApiException

    _session['value'] = session
    return session


def _search(query):
    session = _get_session()
    try:
        response = session.post(_SEARCH_URL, data={
            'q': query,
            'percent': 100,
            'results': 1,
            'bom': 'true',
            'ajax': 'true',
        }, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f'\033[31mERROR\033[0m: API {e}')
        raise ApiException

    if not response.text:
        # A live "no results" answer is still valid JSON (e.g. {"items": []});
        # a truly empty body means the session/endpoint is broken, not that
        # nothing matched -- don't let it look like an ordinary miss.
        print('\033[31mERROR\033[0m: API returned an empty response')
        raise ApiException
    return json.loads(response.text).get('items') or []


class Promelec(BaseProvider):
    sku_column = 'promelec'

    def __init__(self, api_client, item: OrderedDict, qt: int, search_type='mpn', **kwargs) -> None:
        self.qt = qt
        self.item = item
        self.search_type = search_type
        self.rewrite = kwargs.get('rewrite_field')

    @classmethod
    def check_auth(cls):
        try:
            _get_session()
            return True
        except ApiException:
            return False

    @property
    def required_keys(self):
        return ['promelec_sku', 'promelec_mpn', 'promelec_stock', 'promelec_price', 'promelec_consistent', 'promelec_enough']

    def validate(self):
        self.search_by = self._get_search_by(self.search_type)

    def update_with_data(self):
        items = _search(self.search_by)
        if not items:
            raise MissingDataException

        row = items[0]
        sku = str(row.get('id'))
        mpn = row.get('G_NAME')

        vendor = self._pick_vendor(row.get('PRICES') or [])
        if vendor is None:
            raise MissingDataException

        stock = vendor.get('QUANT', 0)
        price = self._get_price(vendor.get('PRICEBREAKS') or [])
        consistent = bool((self.item.get('promelec') == sku) and (self.item.get('mpn') == mpn))
        enough = bool(self.qt <= stock)

        data = [sku, mpn, stock, price, consistent, enough]
        self._update(data)
        self._rewrite(sku, mpn)

    def _pick_vendor(self, prices):
        # Prefer the shortest-lead-time (DELIVERY, days) vendor that can cover qty; else the one with the most stock.
        if not prices:
            return None
        for vendor in sorted(prices, key=lambda v: v.get('DELIVERY', 0)):
            if vendor.get('QUANT', 0) >= self.qt:
                return vendor
        return max(prices, key=lambda v: v.get('QUANT', 0))

    def _get_price(self, pricebreaks):
        if not pricebreaks:
            return None
        selected = None
        for tier in sorted(pricebreaks, key=lambda t: t['QUANT']):
            if tier['QUANT'] <= self.qt:
                selected = tier['PRICE']
        if selected is None:
            selected = min(pricebreaks, key=lambda t: t['QUANT'])['PRICE']
        return rub_to_usd(float(selected))

    def _get_search_by(self, search_type):
        search_by = None
        if search_type == 'mpn':
            search_by = self.item.get('mpn').strip()
        elif search_type == 'sku':
            sku = self.item.get('promelec')
            search_by = f'^{sku.strip()}^' if sku else None
        if search_by:
            return search_by
        raise MissingDataException
