#!/usr/bin/env python3
"""Check the built root filesystem and collect device-specific firmware."""

import hashlib
import json
import pathlib
import shutil
import sys

root = pathlib.Path(sys.argv[1]).resolve()
destination = pathlib.Path(sys.argv[2]).resolve()
metadata = json.loads((root / 'xray-prebuilt/release.json').read_text())
installed = list(root.glob('staging_dir/target-*/root-mediatek/usr/bin/xray'))
if len(installed) != 1:
    sys.exit(f'Expected one installed Xray binary, found {len(installed)}.')
installed_hash = hashlib.sha256(installed[0].read_bytes()).hexdigest()
if installed_hash != metadata['binary_sha256']:
    sys.exit('The firmware root filesystem does not contain the selected Xray binary.')

images_dir = root / 'bin/targets/mediatek/filogic'
images = sorted(images_dir.glob('*tenda_be12-pro*'))
if not any('sysupgrade' in image.name and image.suffix == '.bin' for image in images):
    sys.exit('No Tenda BE12 Pro sysupgrade image was produced.')
destination.mkdir(parents=True, exist_ok=True)
for image in images:
    if image.is_file():
        shutil.copy2(image, destination / image.name)
manifests = sorted(images_dir.glob('*.manifest'))
if not manifests:
    sys.exit('No installed-package manifest was produced for the Release.')
for manifest in manifests:
    shutil.copy2(manifest, destination / manifest.name)
shutil.copy2(root / 'xray-prebuilt/release.json', destination / 'xray-release.json')
shutil.copy2(root / 'source-commit.txt', destination / 'immortalwrt-commit.txt')
shutil.copy2(root / 'source-metadata.json', destination / 'source-metadata.json')
checksums = []
for path in sorted(destination.iterdir()):
    if path.is_file():
        checksums.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')
(destination / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
print(f'Collected {len(images)} device files; installed Xray SHA-256 matches {metadata["tag"]}.')
