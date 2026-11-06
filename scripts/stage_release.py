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

SKIP = {'SHA256SUMS'}


def groups(release_dir):
    """Return (directory, variant) pairs for both supported layouts.

    The publish job downloads each artifact into its own directory. Keep a
    fallback for a single-artifact pattern download, where download-artifact@v4
    flattens the files into release/ itself.
    """
    groups = [(p, p.name.removeprefix('firmware-'))
              for p in sorted(release_dir.iterdir()) if p.is_dir()]
    record = release_dir / 'variant.json'
    if record.is_file():
        try:
            variant = json.loads(record.read_text())['variant']
        except (KeyError, json.JSONDecodeError):
            return groups
        # Never stage the same variant twice when both layouts are present.
        if variant not in {name for _, name in groups}:
            groups.append((release_dir, variant))
    return groups


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
