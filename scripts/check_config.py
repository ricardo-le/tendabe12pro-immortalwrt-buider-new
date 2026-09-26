#!/usr/bin/env python3
"""Fail if make defconfig drops the device or required packages."""

import pathlib
import sys

required = {
    'CONFIG_TARGET_mediatek_filogic_DEVICE_tenda_be12-pro=y',
    'CONFIG_PACKAGE_luci-app-passwall=y',
    'CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Xray=y',
    'CONFIG_PACKAGE_xray-core=y',
}
actual = set(pathlib.Path(sys.argv[1]).read_text().splitlines())
missing = sorted(required - actual)
if missing:
    sys.exit('Required configuration was dropped:\n' + '\n'.join(missing))
print('Tenda BE12 Pro, Passwall, and Xray are selected.')
