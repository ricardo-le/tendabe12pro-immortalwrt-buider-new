#!/usr/bin/env python3
"""Fail if make defconfig drops the device or the variant's packages.

Usage: check_config.py <config> <variant>
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import variants


def check(config_path, variant):
    spec = variants.VARIANTS[variant]
    lines = set(pathlib.Path(config_path).read_text().splitlines())
    missing = [line for line in spec['required'] if line not in lines]
    forbidden = [line for line in spec['forbidden'] if line in lines]
    for prefix in spec.get('forbidden_prefixes', []):
        forbidden += [line for line in lines if line.startswith(prefix) and line.endswith('=y')]
    if missing:
        print('Required configuration was dropped:', file=sys.stderr)
        print('\n'.join('  ' + line for line in missing), file=sys.stderr)
    if forbidden:
        print('Configuration still selects packages this variant must not ship:', file=sys.stderr)
        print('\n'.join('  ' + line for line in forbidden), file=sys.stderr)
    if missing or forbidden:
        sys.exit(1)
    print(f'{variant}: device, packages and kernel options are selected')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: check_config.py <config> <passwall|honk>')
    check(sys.argv[1], sys.argv[2])
