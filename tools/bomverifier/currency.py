import xml.etree.ElementTree as ET
from os import getenv

import requests

from bomverifier.api import DEFAULT_USER_AGENT, get_proxies
from bomverifier.exceptions import ApiException

_CBR_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'

# Cached at module scope so the rate is fetched once per process, not once per BOM row.
_rate = {'value': None}


def rub_to_usd(amount_rub):
    if amount_rub is None:
        return None
    return amount_rub / _get_rate()


def _get_rate():
    if _rate['value'] is not None:
        return _rate['value']

    override = getenv('RUB_USD_RATE')
    if override:
        _rate['value'] = float(override)
        return _rate['value']

    headers = {'User-Agent': getenv('USERAGENT', DEFAULT_USER_AGENT)}
    try:
        response = requests.get(_CBR_URL, headers=headers, proxies=get_proxies(), timeout=30)
        response.raise_for_status()
        # Bytes (not .text): the feed is windows-1251, and ET reads that off the XML prolog itself.
        root = ET.fromstring(response.content)
        valute = root.find(".//Valute[CharCode='USD']")
        nominal = float(valute.findtext('Nominal').replace(',', '.'))
        value = float(valute.findtext('Value').replace(',', '.'))
    except (requests.RequestException, ET.ParseError, AttributeError, TypeError) as e:
        raise ApiException(f'CBR rate {e}') from e

    _rate['value'] = value / nominal
    return _rate['value']
