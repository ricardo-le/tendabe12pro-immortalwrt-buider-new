#!/usr/bin/env python3
"""Stage the honk LuCI page from upstream, or from the vendored baseline.

The page (luci-app-honk + luci-lib-daeuniverse) is plain JavaScript, JSON and
one shell script, so there is nothing to compile: staging is a file copy.

By default the files are taken from the newest commit of upstream main, the same
way the honk binary follows the newest release. When GitHub cannot be reached,
the copy vendored in this repository is used instead, so an upstream outage
never fails a build; the metadata records which one was used.

Pin a revision with LUCI_APPS_REF=<commit|tag|branch> (default: main).
"""

import json
import os
import pathlib
import shutil
import sys
import time
import urllib.error
import urllib.request

PROJECT = 'daeuniverse/openwrt-packages'
API = f'https://api.github.com/repos/{PROJECT}'
RAW = f'https://raw.githubusercontent.com/{PROJECT}'
DEFAULT_REF = 'main'

PACKAGES = ('luci-app-honk', 'luci-lib-daeuniverse')

# The commit the vendored copy in package/ was taken from. Must match
# package/VENDORED.md; only used when the network fetch fails.
BASELINE_COMMIT = 'e48b222f239e2572244c8cf495fbce79b0da7528'

# A rename upstream would stage a page that cannot work, so the file set is
# verified instead of trusting whatever the tree happens to contain.
REQUIRED = (
    'luci-app-honk/Makefile',
    'luci-app-honk/htdocs/luci-static/resources/honk/nativeapi.js',
    'luci-app-honk/htdocs/luci-static/resources/view/honk/main.js',
    'luci-app-honk/root/usr/share/luci/menu.d/luci-app-honk.json',
    'luci-app-honk/root/usr/share/rpcd/acl.d/luci-app-honk.json',
    'luci-lib-daeuniverse/Makefile',
    'luci-lib-daeuniverse/htdocs/luci-static/resources/daeuniverse/service.js',
    'luci-lib-daeuniverse/root/usr/libexec/daeuniverse-pkg',
)

EXECUTABLE = frozenset({
    'luci-lib-daeuniverse/root/usr/libexec/daeuniverse-pkg',
})


def fetch(url, attempts=4, timeout=45):
    """GET url, retrying transient failures. GitHub drops connections often."""
    headers = {'User-Agent': 'tenda-be12-pro-firmware', 'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GITHUB_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = f'Bearer {token}'
    error = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # A 404 or a rate limit will not fix itself within seconds.
            if exc.code < 500:
                raise RuntimeError(f'{url}: HTTP {exc.code}') from exc
            error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            error = exc
        if attempt < attempts:
            time.sleep(2 * attempt)
    raise RuntimeError(f'{url}: {error}')


def resolve(ref):
    """Return the commit a ref points at, so every download uses the same tree."""
    payload = json.loads(fetch(f'{API}/commits/{ref}'))
    return payload['sha'], (payload.get('commit', {}).get('committer', {}) or {}).get('date', '')


def listing(commit):
    tree = json.loads(fetch(f'{API}/git/trees/{commit}?recursive=1'))
    if tree.get('truncated'):
        raise RuntimeError('the upstream tree listing is truncated')
    return {item['path'] for item in tree.get('tree', [])
            if item.get('type') == 'blob' and item['path'].startswith(PACKAGES)}


def _write(root, files):
    for package in PACKAGES:
        shutil.rmtree(root / 'package' / package, ignore_errors=True)
    for path, data in sorted(files.items()):
        destination = root / 'package' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o755 if path in EXECUTABLE else 0o644)


def _stage_upstream(root, ref):
    commit, date = resolve(ref)
    available = listing(commit)
    missing = sorted(set(REQUIRED) - available)
    if missing:
        raise RuntimeError('upstream has no ' + ', '.join(missing))
    files = {path: fetch(f'{RAW}/{commit}/{path}') for path in sorted(available)}
    _write(root, files)
    return {
        'repository': PROJECT,
        'ref': ref,
        'commit': commit,
        'commit_date': date,
        'source': 'upstream',
        'files': sorted(files),
    }


def _stage_vendored(root, repo, ref, reason):
    for package in PACKAGES:
        source = repo / 'package' / package
        missing = [p for p in REQUIRED if p.startswith(package + '/')
                   and not (repo / 'package' / p).is_file()]
        if missing:
            sys.exit('vendored baseline is incomplete: ' + ', '.join(missing))
        shutil.copytree(source, root / 'package' / package, dirs_exist_ok=True)
        for path in EXECUTABLE:
            if path.startswith(package + '/'):
                (root / 'package' / path).chmod(0o755)
    return {
        'repository': PROJECT,
        'ref': ref,
        'commit': BASELINE_COMMIT,
        'commit_date': '',
        'source': 'vendored',
        'reason': str(reason),
        'files': sorted(REQUIRED),
    }


def stage(root, repo, ref=None):
    """Stage both LuCI packages under root/package and record where they came from."""
    root = pathlib.Path(root).resolve()
    repo = pathlib.Path(repo).resolve()
    ref = ref or os.environ.get('LUCI_APPS_REF') or DEFAULT_REF

    try:
        metadata = _stage_upstream(root, ref)
        print(f'luci: using {PROJECT}@{ref} ({metadata["commit"][:12]})')
    except Exception as exc:  # noqa: BLE001 - any failure falls back on purpose
        print(f'warning: cannot fetch {PROJECT}@{ref} ({exc}); '
              'using the vendored copy in package/', file=sys.stderr)
        metadata = _stage_vendored(root, repo, ref, exc)
        print(f'luci: using the vendored baseline {BASELINE_COMMIT[:12]}')

    (root / 'luci-apps.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: fetch_luci.py <immortalwrt-root> [repo-root] [ref]')
    stage(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '.',
          sys.argv[3] if len(sys.argv) > 3 else None)
