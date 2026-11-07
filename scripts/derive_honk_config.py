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
HONK_OPTIONS = {
    **{f'CONFIG_PACKAGE_{name}': 'y' for name in variants.HONK_EXTRA_PACKAGES},
    'CONFIG_KERNEL_CGROUPS': 'y',
    'CONFIG_KERNEL_CGROUP_BPF': 'y',
    'CONFIG_KERNEL_DEBUG_INFO': 'y',
    'CONFIG_KERNEL_DEBUG_INFO_REDUCED': 'n',
    # Detached BTF belongs in rootfs, never in the 6 MiB kernel partition.
    'CONFIG_KERNEL_DEBUG_INFO_BTF': 'n',
}


def key_of(line):
    line = line.strip()
    if line.startswith('# '):
        line = line[2:]
    return line.split('=')[0].replace(' is not set', '').strip()


def transform(lines):
    output = []
    disabled = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith('CONFIG_') or stripped.startswith('# CONFIG_')):
            output.append(line)
            continue
        key = key_of(stripped)
        if key in HONK_OPTIONS:
            if key not in seen:
                value = HONK_OPTIONS[key]
                output.append(f'# {key} is not set' if value == 'n' else f'{key}={value}')
                seen.add(key)
            continue
        if key.startswith(REMOVED_PREFIXES) or key in REMOVED_EXACT:
            # Keep the symbol with an explicit "not set" instead of deleting the
            # line: the luci-app-passwall_INCLUDE_* booleans have no dependency
            # on the app itself and default to y on arm64, so a deleted line
            # comes back as "=y" on the next defconfig and makes the honk config
            # look as if Passwall were selected.
            output.append(f'# {key} is not set')
            disabled.append(key)
            continue
        output.append(line)
    for key, value in HONK_OPTIONS.items():
        if key not in seen:
            output.append(f'# {key} is not set' if value == 'n' else f'{key}={value}')
    return output, disabled


def main(source, target):
    source = pathlib.Path(source)
    target = pathlib.Path(target)
    lines = source.read_text().splitlines()
    output, removed = transform(lines)

    header = [
        '# Derived from tendabe12pro.config by scripts/derive_honk_config.py.',
        '# Do not edit by hand: edit the Passwall config, then re-run the script.',
    ]
    text = '\n'.join(header + output) + '\n'
    target.write_text(text)

    print(f'{target.name}: disabled {len(removed)} Passwall entries')
    for key in removed:
        print(f'  - {key}')
    print(f'{target.name}: enforced {len(HONK_OPTIONS)} honk package/kernel options')
    leftovers = [key_of(line) for line in text.splitlines()
                 if line.startswith('CONFIG_') and line.endswith('=y')
                 and (key_of(line).startswith(REMOVED_PREFIXES) or key_of(line) in REMOVED_EXACT)]
    if leftovers:
        sys.exit('Passwall packages are still selected: ' + ', '.join(leftovers))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else SOURCE,
         sys.argv[2] if len(sys.argv) > 2 else TARGET)
