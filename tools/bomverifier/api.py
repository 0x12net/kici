import json
import time
from os import getenv

import requests

from bomverifier.exceptions import ApiException

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0"


def get_proxies():
    """Build a requests proxies dict from SOCKS5_* env vars, or None."""
    url = getenv('SOCKS5_URL')
    if not url:
        return None
    proxy = f"socks5://{getenv('SOCKS5_USERNAME')}:{getenv('SOCKS5_PASSWORD')}@{url}"
    return {'http': proxy, 'https': proxy}


class ApiClient():

    def __init__(self):
        self.headers = {"User-Agent": getenv('USERAGENT', DEFAULT_USER_AGENT)}
        self.proxies = get_proxies()

    def send_request(self, url, params):
        last_error = None
        for _ in range(3):
            try:
                response = requests.get(url, params=params, headers=self.headers, proxies=self.proxies)
                response.raise_for_status()
                return json.loads(response.text)
            except requests.RequestException as e:
                last_error = e
                time.sleep(3)
        raise ApiException(str(last_error)) from last_error
