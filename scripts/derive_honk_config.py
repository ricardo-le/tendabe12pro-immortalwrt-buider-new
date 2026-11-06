#!/usr/bin/env python3
"""Derive the honk variant config from the Passwall one.

The Passwall config is the menuconfig snapshot maintained on the build
machine, so it stays the single source of truth: this script strips the whole
Passwall stack and the kernel options honk needs changed, then adds honk.

Usage: derive_honk_config.py [source.config] [target.config]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import variants

SOURCE = 'tendabe12pro.config'
TARGET = 'tendabe12pro-honk.config'

REMOVED_PREFIXES = (
    'CONFIG_PACKAGE_luci-app-passwall',
    'CONFIG_PACKAGE_luci-i18n-passwall',
)
REMOVED_EXACT = {f'CONFIG_PACKAGE_{name}' for name in variants.PASSWALL_STACK}


def key_of(line):
    line = line.strip()
    if line.startswith('# '):
        line = line[2:]
    return line.split('=')[0].replace(' is not set', '').strip()


def transform(lines):
    output = []
    disabled = []
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith('CONFIG_') or stripped.startswith('# CONFIG_')):
            output.append(line)
            continue
        key = key_of(stripped)
        if key.startswith(REMOVED_PREFIXES) or key in REMOVED_EXACT:
            # Keep the symbol with an explicit "not set" instead of deleting the
            # line: the luci-app-passwall_INCLUDE_* booleans have no dependency
            # on the app itself and default to y on arm64, so a deleted line
            # comes back as "=y" on the next defconfig and makes the honk config
            # look as if Passwall were selected.
            output.append(f'# {key} is not set')
            disabled.append(key)
            continue
        if key == 'CONFIG_KERNEL_DEBUG_INFO_REDUCED':
            output.append('# CONFIG_KERNEL_DEBUG_INFO_REDUCED is not set')
            continue
        output.append(line)
    return output, disabled


def main(source, target):
    source = pathlib.Path(source)
    target = pathlib.Path(target)
    lines = source.read_text().splitlines()
    output, removed = transform(lines)

    existing = {key_of(line) for line in output if line.strip() and not line.strip().startswith('#')}
    additions = [f'CONFIG_PACKAGE_{name}=y' for name in variants.HONK_EXTRA_PACKAGES
                 if f'CONFIG_PACKAGE_{name}' not in existing]

    header = [
        '# Derived from tendabe12pro.config by scripts/derive_honk_config.py.',
        '# Do not edit by hand: edit the Passwall config, then re-run the script.',
    ]
    text = '\n'.join(header + output + additions) + '\n'
    target.write_text(text)

    print(f'{target.name}: disabled {len(removed)} Passwall entries')
    for key in removed:
        print(f'  - {key}')
    print(f'{target.name}: added {len(additions)} honk entries')
    for line in additions:
        print(f'  + {line}')
    leftovers = [key_of(line) for line in text.splitlines()
                 if line.startswith('CONFIG_') and line.endswith('=y')
                 and (key_of(line).startswith(REMOVED_PREFIXES) or key_of(line) in REMOVED_EXACT)]
    if leftovers:
        sys.exit('Passwall packages are still selected: ' + ', '.join(leftovers))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else SOURCE,
         sys.argv[2] if len(sys.argv) > 2 else TARGET)
