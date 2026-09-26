#!/usr/bin/env python3
"""Replace the feed's source-built Xray package with an official ARM64 release."""

import hashlib
import io
import json
import os
import pathlib
import re
import struct
import sys
import urllib.request
import zipfile

API = 'https://api.github.com/repos/XTLS/Xray-core/releases?per_page=100'
ASSET = 'Xray-linux-arm64-v8a.zip'


def fetch(url):
    headers = {'User-Agent': 'tenda-be12-pro-firmware', 'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GITHUB_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return response.read()


def choose_release(releases):
    published = [item for item in releases if not item['draft'] and item.get('published_at')]
    if not published:
        raise ValueError('No published Xray release was found')
    release = max(published, key=lambda item: item['published_at'])
    for asset in release['assets']:
        if asset['name'] == ASSET:
            return release, asset
    raise ValueError('Newest published Xray release lacks ' + ASSET)


def package_makefile(version):
    if not re.fullmatch(r'[0-9][A-Za-z0-9._-]*', version):
        raise ValueError('Unexpected Xray tag: ' + version)
    return f'''include $(TOPDIR)/rules.mk

PKG_NAME:=xray-core
PKG_VERSION:={version}
PKG_RELEASE:=1
PKG_LICENSE:=MPL-2.0
PKG_BUILD_DIR:=$(BUILD_DIR)/xray-core-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/xray-core
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Xray proxy platform (official Linux ARM64 binary)
  URL:=https://github.com/XTLS/Xray-core
  DEPENDS:=+ca-bundle
endef

define Package/xray-core/description
  Official Xray Linux ARM64 v8a release binary.
endef

define Package/xray-core/conffiles
/etc/xray/
/etc/config/xray
endef

define Build/Prepare
\tmkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/xray-core/install
\t$(INSTALL_DIR) $(1)/usr/bin
\t$(INSTALL_BIN) $(TOPDIR)/xray-prebuilt/xray $(1)/usr/bin/xray
\t$(INSTALL_DIR) $(1)/etc/xray
\t$(INSTALL_DATA) $(CURDIR)/files/config.json.example $(1)/etc/xray/
\t$(INSTALL_DIR) $(1)/etc/config
\t$(INSTALL_CONF) $(CURDIR)/files/xray.conf $(1)/etc/config/xray
\t$(INSTALL_DIR) $(1)/etc/init.d
\t$(INSTALL_BIN) $(CURDIR)/files/xray.init $(1)/etc/init.d/xray
endef

$(eval $(call BuildPackage,xray-core))
'''


def main(root):
    feed_package = root / 'feeds/packages/net/xray-core'
    if not (feed_package / 'files/xray.init').is_file():
        sys.exit('ImmortalWrt xray-core feed layout changed; stopping build.')
    release, asset = choose_release(json.loads(fetch(API)))
    tag = release['tag_name']
    version = tag.removeprefix('v')
    expected = asset.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', expected):
        sys.exit('Xray release asset has no valid SHA-256 digest; stopping build.')
    archive = fetch(asset['browser_download_url'])
    actual = hashlib.sha256(archive).hexdigest()
    if actual != expected[7:]:
        sys.exit(f'Xray archive checksum mismatch: expected {expected[7:]}, got {actual}')
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = [name for name in zf.namelist() if name.rsplit('/', 1)[-1] == 'xray']
        if len(names) != 1:
            sys.exit('Expected exactly one xray binary in official archive.')
        binary = zf.read(names[0])
    if binary[:4] != b'\x7fELF' or binary[4] != 2 or binary[5] != 1 or struct.unpack_from('<H', binary, 18)[0] != 183:
        sys.exit('Downloaded Xray binary is not a 64-bit little-endian AArch64 ELF.')
    prebuilt = root / 'xray-prebuilt'
    prebuilt.mkdir(exist_ok=True)
    path = prebuilt / 'xray'
    path.write_bytes(binary)
    path.chmod(0o755)
    (feed_package / 'Makefile').write_text(package_makefile(version))
    metadata = {'tag': tag, 'prerelease': release['prerelease'], 'asset': ASSET,
                'archive_sha256': actual, 'binary_sha256': hashlib.sha256(binary).hexdigest()}
    (prebuilt / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]).resolve())
