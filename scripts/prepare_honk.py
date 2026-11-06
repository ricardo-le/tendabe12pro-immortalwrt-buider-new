#!/usr/bin/env python3
"""Stage the honk variant: official binary and local packages.

Everything here is deterministic and verified:

* the honk-core binary comes from the pinned upstream release, its SHA-256 is
  checked against the release's own SHA256SUMS asset and against the digest
  GitHub reports for the asset, and the ELF header is checked to be a 64-bit
  little-endian AArch64 executable;
* the local packages (honk, vmlinux-btf-local) are copied into the buildroot.

Kernel options are not touched here: CONFIG_KERNEL_* in the variant config is
the supported way to change the kernel, because Kernel/Configure/Default copies
those symbols into the kernel .config with the KERNEL_ prefix stripped.
"""

import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

DEFAULT_TAG = 'v0.1.0-beta.5'
REPO = 'daeuniverse/honk'
ASSET_TEMPLATE = 'honk-core-{tag}-aarch64-unknown-linux-musl-full.tar.gz'


def fetch(url):
    headers = {'User-Agent': 'tenda-be12-pro-firmware', 'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GITHUB_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def package_version(tag):
    """v0.1.0-beta.5 -> 0.1.0_beta5 (a version apk/opkg accepts)."""
    version = tag.removeprefix('v')
    return re.sub(r'-(alpha|beta|rc)\.', r'_\1', version)


def release(tag):
    payload = json.loads(fetch(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}'))
    if payload.get('draft'):
        sys.exit(f'honk {tag} is still a draft release')
    return payload


def asset_by_name(release_payload, name):
    for asset in release_payload['assets']:
        if asset['name'] == name:
            return asset
    available = ', '.join(sorted(a['name'] for a in release_payload['assets']))
    sys.exit(f'honk release {release_payload["tag_name"]} has no {name}\navailable: {available}')


def checksums(release_payload):
    asset = asset_by_name(release_payload, 'SHA256SUMS')
    text = fetch(asset['browser_download_url']).decode()
    table = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            table[parts[1].lstrip('*')] = parts[0].lower()
    if not table:
        sys.exit('honk SHA256SUMS is empty')
    return table


def verify_elf(binary):
    if len(binary) < 64 or binary[:4] != b'\x7fELF':
        sys.exit('honk-core is not an ELF file')
    if binary[4] != 2 or binary[5] != 1:
        sys.exit('honk-core is not a 64-bit little-endian ELF')
    if struct.unpack_from('<H', binary, 18)[0] != 183:
        sys.exit('honk-core is not an AArch64 binary')
    if len(binary) < 1024 * 1024:
        sys.exit(f'honk-core is suspiciously small ({len(binary)} bytes)')


def check_pahole():
    """Fail at minute two, not hour two, when the host pahole cannot do BTF.

    A pahole older than 1.24 has --btf_encode_detached but aborts on the
    DW_TAG_unspecified_type that GCC 14 emits for the 6.18 kernel, so the
    version matters, not just the option.
    """
    try:
        result = subprocess.run(['pahole', '--help'], text=True, capture_output=True)
        version = subprocess.run(['pahole', '--version'], text=True, capture_output=True).stdout
    except FileNotFoundError:
        sys.exit('pahole is required for the honk variant; build dwarves >= 1.24 from source')
    help_text = (result.stdout or '') + (result.stderr or '')
    if 'btf_encode_detached' not in help_text:
        sys.exit('pahole is too old: --btf_encode_detached is missing (needs >= 1.24)')
    match = re.search(r'v?(\d+)\.(\d+)', version)
    if not match:
        sys.exit(f'cannot parse the pahole version: {version.strip()!r}')
    if (int(match.group(1)), int(match.group(2))) < (1, 24):
        sys.exit(f'pahole {version.strip()} is too old: kernels >= 6.18 need '
                 'DW_TAG_unspecified_type support, which landed in 1.24')


def prepare(root, repo, tag=None):
    root = pathlib.Path(root).resolve()
    repo = pathlib.Path(repo).resolve()
    check_pahole()
    tag = tag or os.environ.get('HONK_TAG') or DEFAULT_TAG
    name = ASSET_TEMPLATE.format(tag=tag)

    release_payload = release(tag)
    asset = asset_by_name(release_payload, name)
    table = checksums(release_payload)
    if name not in table:
        sys.exit(f'SHA256SUMS of honk {tag} does not list {name}')

    archive = fetch(asset['browser_download_url'])
    digest = hashlib.sha256(archive).hexdigest()
    if digest != table[name]:
        sys.exit(f'honk archive checksum mismatch: SHA256SUMS says {table[name]}, got {digest}')
    reported = asset.get('digest') or ''
    if re.fullmatch(r'sha256:[0-9a-f]{64}', reported) and reported[7:] != digest:
        sys.exit(f'honk archive does not match the digest GitHub reports for the asset')

    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tf:
        members = [m for m in tf.getmembers() if m.name.rsplit('/', 1)[-1] == 'honk-core']
        if len(members) != 1 or not members[0].isfile():
            sys.exit(f'expected exactly one honk-core file in {name}')
        binary = tf.extractfile(members[0]).read()
    verify_elf(binary)

    prebuilt = root / 'honk-prebuilt'
    prebuilt.mkdir(exist_ok=True)
    target = prebuilt / 'honk-core'
    target.write_bytes(binary)
    target.chmod(0o755)

    version = package_version(tag)
    metadata = {
        'project': REPO,
        'tag': tag,
        'package_version': version,
        'asset': name,
        'asset_size': len(archive),
        'archive_sha256': digest,
        'binary_sha256': hashlib.sha256(binary).hexdigest(),
        'binary_size': len(binary),
        'prerelease': bool(release_payload.get('prerelease')),
    }
    (prebuilt / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')

    for package in ('honk', 'vmlinux-btf-local'):
        shutil.copytree(repo / 'package' / package, root / 'package' / package, dirs_exist_ok=True)
    (root / 'package/honk/version.mk').write_text(
        '# Written by scripts/prepare_honk.py; mirrors honk-prebuilt/release.json.\n'
        f'HONK_VERSION:={version}\n'
        f'HONK_GIT_TAG:={tag}\n')

    if len(binary) > 64 * 1024 * 1024:
        print(f'warning: honk-core is {len(binary) / 1048576:.1f} MB, check the rootfs budget')
    print(json.dumps(metadata, indent=2))
    print(f'honk packages staged in {root / "package"}')
    return metadata


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: prepare_honk.py <immortalwrt-root> [repo-root]')
    prepare(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '.')
