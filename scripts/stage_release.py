#!/usr/bin/env python3
"""Flatten the per-variant artifacts into one upload directory.

GitHub Release assets live in a single namespace, but both variants produce
files with the same upstream name (…-tenda_be12-pro-squashfs-sysupgrade.bin),
so every asset is prefixed with its variant and one SHA256SUMS covers them all.

Usage: stage_release.py <release-dir> <upload-dir>
"""

import hashlib
import json
import pathlib
import shutil
import sys

import variants

SKIP = {'SHA256SUMS'}


def validate(directory, variant):
    """Reject partial downloads before they enter either assets or notes."""
    record = json.loads((directory / 'variant.json').read_text())
    spec = variants.VARIANTS[variant]
    if record['variant'] != variant or record['payload'] != spec['payload']:
        raise ValueError('variant/payload metadata does not match the artifact name')
    images = record['images']
    if not isinstance(images, list) or not images:
        raise ValueError('no images listed in variant.json')
    if any(not isinstance(name, str) or pathlib.Path(name).name != name
           or variants.DEVICE not in name for name in images):
        raise ValueError('invalid device image filename')
    if not any('sysupgrade' in name and name.endswith('.bin') for name in images):
        raise ValueError('no sysupgrade image listed')
    required = images + ['immortalwrt-commit.txt', 'source-metadata.json',
                         f'{spec["payload"]}-release.json']
    if any(not (directory / name).is_file() or (directory / name).stat().st_size == 0
           for name in required):
        raise ValueError('missing or empty firmware/metadata file')
    if not any(p.is_file() and p.stat().st_size for p in directory.glob('*.manifest')):
        raise ValueError('missing installed-package manifest')
    source = json.loads((directory / 'source-metadata.json').read_text())
    payload = json.loads((directory / f'{spec["payload"]}-release.json').read_text())
    if source['variant'] != variant or not payload['tag']:
        raise ValueError('source/payload metadata does not match the variant')


def groups(release_dir):
    """Return complete known variants, accepting fixed and flat layouts."""
    found = []
    flat_variant = None
    record = release_dir / 'variant.json'
    if record.is_file():
        try:
            flat_variant = json.loads(record.read_text())['variant']
        except (KeyError, TypeError, ValueError, OSError):
            pass
    for variant in variants.VARIANTS:
        candidates = [release_dir / f'firmware-{variant}', release_dir / variant]
        if flat_variant == variant:
            candidates.append(release_dir)
        for directory in candidates:
            if not directory.is_dir():
                continue
            try:
                validate(directory, variant)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                print(f'warning: skipping incomplete {variant} artifact at {directory}: {exc}',
                      file=sys.stderr)
                continue
            found.append((directory, variant))
            break
    return found


def main(release_dir, upload_dir):
    release_dir = pathlib.Path(release_dir)
    upload_dir = pathlib.Path(upload_dir)
    # Both artifact downloads use continue-on-error, so this directory may not
    # exist at all when a run produced nothing; fail with a clear message
    # instead of a traceback from iterdir().
    if not release_dir.is_dir():
        sys.exit(f'no firmware artifacts under {release_dir}')
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    upload_dir.mkdir(parents=True)

    staged = 0
    variants = []
    for directory, variant in groups(release_dir):
        files = [p for p in sorted(directory.iterdir()) if p.is_file() and p.name not in SKIP]
        if not files:
            continue
        variants.append(variant)
        for path in files:
            name = path.name if path.name.startswith(f'{variant}-') else f'{variant}-{path.name}'
            shutil.copy2(path, upload_dir / name)
            staged += 1

    if not staged:
        sys.exit(f'no firmware artifacts under {release_dir}')

    lines = []
    for path in sorted(upload_dir.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS':
            lines.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')
    (upload_dir / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print(f'staged {staged} files for: {", ".join(variants)}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: stage_release.py <release-dir> <upload-dir>')
    main(sys.argv[1], sys.argv[2])
