import argparse
import re
import sys
import time
from pathlib import Path

import requests

from bomverifier.api import get_proxies


def log(message):
    """Diagnostics go to stderr - stdout carries only the `export VAR=...` lines."""
    print(message, file=sys.stderr)


MODEL_RE = re.compile(r'\(model\s+"\$\{(\w+)\}/([^"]+)"')


def find_models(pcb_file):
    """Yield unique (var, relative_path) pairs from (model "${VAR}/...") references."""
    seen = set()
    for var, rel_path in MODEL_RE.findall(Path(pcb_file).read_text()):
        if (var, rel_path) not in seen:
            seen.add((var, rel_path))
            yield var, rel_path


def parse_repos(spec):
    """Parse VAR=URL lines (blank/# lines ignored) into {var: base_url}."""
    repos = {}
    for line in spec.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        var, sep, url = line.partition('=')
        if not sep:
            log(f'WARN: ignoring malformed MODELS3D_REPOS line: {line!r}')
            continue
        repos[var.strip()] = url.strip().rstrip('/')
    return repos


def download(url, dest, proxies):
    dest.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            response = requests.get(url, proxies=proxies, timeout=30)
            response.raise_for_status()
            dest.write_bytes(response.content)
            return True
        except requests.RequestException as e:
            log(f'\033[31mERROR\033[0m: download {url}: {e}')
            time.sleep(3)
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Download only the 3D models referenced by a kicad_pcb file, '
                    'from per-variable repos, instead of bundling the whole library')
    parser.add_argument('pcb_file', help='*.kicad_pcb file to scan for (model "${VAR}/...") references')
    parser.add_argument('-r', '--repos', required=True,
                         help='VAR=URL pairs, one per line; URL is the raw base of the folder tree '
                              'matching ${VAR} (e.g. KICAD9_3DMODEL_DIR=https://gitlab.com/kicad/'
                              'libraries/kicad-packages3D/-/raw/master)')
    parser.add_argument('-o', '--cache-dir', default='3dmodels_cache',
                         help='Local directory to download models into (reused across calls, keyed by var/path)')
    args = parser.parse_args()

    repos = parse_repos(args.repos)
    cache_dir = Path(args.cache_dir)
    proxies = get_proxies()

    used_vars, missing = set(), []
    for var, rel_path in find_models(args.pcb_file):
        used_vars.add(var)
        base_url = repos.get(var)
        if base_url is None:
            missing.append((var, rel_path, 'no repo configured for this variable'))
            continue
        dest = cache_dir / var / rel_path
        if dest.exists():
            continue
        log(f'INFO: downloading {base_url}/{rel_path}')
        if not download(f'{base_url}/{rel_path}', dest, proxies):
            missing.append((var, rel_path, 'download failed'))

    if missing:
        log(f'WARN: {len(missing)} model(s) not available locally '
            f'(kicad-cli --subst-models will substitute or skip them):')
        for var, rel_path, reason in missing:
            log(f'  - ${{{var}}}/{rel_path} ({reason})')

    for var in sorted(used_vars):
        if var in repos:
            print(f'export {var}="{(cache_dir / var).resolve()}"')


if __name__ == '__main__':
    main()
