import os
import time
from urllib.parse import quote

import requests

from bomverifier.api import ApiClient
from bomverifier.exceptions import MissingDataException, ApiException
from bomverifier.base import BaseProvider


# DigiKey Product Information API v4 with 2-legged OAuth (client credentials).
# Only DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET are required — no interactive
# browser login and no persistent token cache, which makes it CI-friendly.
# Set DIGIKEY_CLIENT_SANDBOX=True to target the sandbox host.

_PROD_HOST = 'https://api.digikey.com'
_SANDBOX_HOST = 'https://sandbox-api.digikey.com'

# Access token shared across BOM rows. ApiClient is rebuilt for every row, so the
# token must live at module scope to avoid one auth request per row.
_token = {'value': None, 'expires_at': 0.0}


def _base_host():
    sandbox = os.getenv('DIGIKEY_CLIENT_SANDBOX', 'False').strip().lower() in ('1', 'true', 'yes')
    return _SANDBOX_HOST if sandbox else _PROD_HOST


def _proxies():
    url = os.getenv('SOCKS5_URL')
    if not url:
        return None
    proxy = f"socks5://{os.getenv('SOCKS5_USERNAME')}:{os.getenv('SOCKS5_PASSWORD')}@{url}"
    return {'http': proxy, 'https': proxy}


def _get_access_token():
    now = time.time()
    if _token['value'] and now < _token['expires_at']:
        return _token['value']

    client_id = os.getenv('DIGIKEY_CLIENT_ID')
    client_secret = os.getenv('DIGIKEY_CLIENT_SECRET')
    if not client_id or not client_secret:
        print('\033[31mERROR\033[0m: DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET are not set')
        raise ApiException

    try:
        resp = requests.post(
            f'{_base_host()}/v1/oauth2/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials',
            },
            proxies=_proxies(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f'\033[31mERROR\033[0m: DigiKey auth {e}')
        raise ApiException

    _token['value'] = data['access_token']
    # Refresh slightly early so a nearly expired token is never used mid-run.
    _token['expires_at'] = now + int(data.get('expires_in', 599)) - 30
    return _token['value']


class DigiKey(BaseProvider):
    sku_column = 'digikey'

    def __init__(self, api_client: ApiClient, item, qt: int, search_type='mpn', **kwargs) -> None:
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
        host = _base_host()
        if self.search_type == 'sku':
            url = f'{host}/products/v4/search/{quote(self.search_by, safe="")}/productdetails'
            product = self._request('GET', url).get('Product')
        else:
            url = f'{host}/products/v4/search/keyword'
            data = self._request('POST', url, json={'Keywords': self.search_by, 'Limit': 1})
            products = data.get('Products') or []
            product = products[0] if products else None

        if not product:
            self.fill_with_empty_values()
            return

        mpn = product.get('ManufacturerProductNumber')
        stock = product.get('QuantityAvailable') or 0
        variation = self._pick_variation(product.get('ProductVariations') or [])
        sku = variation.get('DigiKeyProductNumber') if variation else None
        price = self._get_price(variation.get('StandardPricing') if variation else None)
        consistent = bool((self.item.get('digikey') == sku) and (self.item.get('mpn') == mpn))
        enough = bool(self.qt <= int(stock))

        self._update([sku, mpn, stock, price, consistent, enough])
        self._rewrite(sku, mpn)

    def _request(self, method, url, **kwargs):
        headers = {
            'Authorization': f'Bearer {_get_access_token()}',
            'X-DIGIKEY-Client-Id': os.getenv('DIGIKEY_CLIENT_ID'),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            # Locale is fixed so pricing/currency is deterministic; adjust if needed.
            'X-DIGIKEY-Locale-Site': 'US',
            'X-DIGIKEY-Locale-Language': 'en',
            'X-DIGIKEY-Locale-Currency': 'USD',
            'User-Agent': os.getenv('USERAGENT', 'Mozilla/5.0'),
        }
        try:
            resp = requests.request(method, url, headers=headers, proxies=_proxies(), timeout=30, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f'\033[31mERROR\033[0m: API {e}')
            raise ApiException

    def _pick_variation(self, variations):
        """A product exposes one variation per packaging option, each with its own
        DigiKey part number and pricing. When searching by sku, keep the variation
        that matches it; otherwise take the first one that has a part number."""
        if not variations:
            return None
        if self.search_type == 'sku':
            for v in variations:
                if v.get('DigiKeyProductNumber') == self.search_by:
                    return v
        for v in variations:
            if v.get('DigiKeyProductNumber'):
                return v
        return variations[0]

    def _get_price(self, price_breaks):
        if not price_breaks:
            return None
        selected = None
        for tier in sorted(price_breaks, key=lambda p: p.get('BreakQuantity', 0)):
            if tier.get('BreakQuantity', 0) <= self.qt:
                selected = tier.get('UnitPrice')
        # qty below the smallest break: fall back to the lowest-quantity price
        # so a price is still reported instead of an empty cell.
        if selected is None:
            lowest = min(price_breaks, key=lambda p: p.get('BreakQuantity', 0))
            selected = lowest.get('UnitPrice')
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
