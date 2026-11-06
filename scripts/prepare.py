#!/usr/bin/env python3
"""Prepare one firmware variant inside the ImmortalWrt buildroot.

Usage: prepare.py <variant> [--root immortalwrt] [--repo .]

Steps, in the only order that works:
  1. stage the variant's payload (official Xray binary, or honk + kernel bits),
  2. copy the variant's config to .config and run `make defconfig`,
  3. fail if defconfig dropped the device or the variant's packages,
  4. record the upstream revisions the build actually used.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_config
import prepare_honk
import prepare_xray
import record_sources
import variants


def disable_options(config, prefixes):
    """Turn off selected options whose names start with one of the prefixes."""
    if not prefixes:
        return []
    lines = config.read_text().splitlines()
    changed = []
    for index, line in enumerate(lines):
        if line.endswith('=y') and any(line.startswith(prefix) for prefix in prefixes):
            key = line.split('=', 1)[0]
            lines[index] = f'# {key} is not set'
            changed.append(key)
    if changed:
        config.write_text('\n'.join(lines) + '\n')
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=sorted(variants.VARIANTS))
    parser.add_argument('--root', default='immortalwrt', help='ImmortalWrt checkout')
    parser.add_argument('--repo', default='.', help='this builder repository')
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    repo = pathlib.Path(args.repo).resolve()
    spec = variants.VARIANTS[args.variant]

    if args.variant == 'honk':
        prepare_honk.prepare(root, repo)
    else:
        prepare_xray.prepare(root)

    config = root / '.config'
    shutil.copyfile(repo / spec['config'], config)
    subprocess.run(['make', 'defconfig'], cwd=root, check=True)

    # A feed may add sub-options after the base config was generated (Passwall
    # gained INCLUDE_SmartDNS in Nov 2026), and those default to y on arm64
    # without depending on the package itself. They are inert, but the honk
    # config must not look as if Passwall were selected, so switch them off and
    # let kconfig settle the result.
    disabled = disable_options(config, spec.get('forbidden_prefixes', []))
    if disabled:
        print(f'{args.variant}: disabled {len(disabled)} inherited options: ' + ', '.join(disabled))
        subprocess.run(['make', 'defconfig'], cwd=root, check=True)

    check_config.check(config, args.variant)
    record_sources.record(root, repo / spec['config'], args.variant)
    print(f'{args.variant}: buildroot prepared')


if __name__ == '__main__':
    main()
