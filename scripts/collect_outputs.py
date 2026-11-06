#!/usr/bin/env python3
"""Verify the built root filesystem and collect the device firmware.

Usage: collect_outputs.py <immortalwrt-root> <destination> <variant>
"""

import hashlib
import json
import pathlib
import re
import shutil
import sys
import tarfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import variants

KERNEL_LIMIT = variants.KERNEL_PARTITION_BYTES


def kernel_size(image):
    """Size of the kernel member of the sysupgrade tar, or None.

    A None result is a hard failure in collect(): silently skipping the size
    check would defeat the guarantee that no unbootable image is published.
    """
    try:
        with tarfile.open(image, 'r:*') as archive:
            for member in archive.getmembers():
                if member.name.rsplit('/', 1)[-1] == 'kernel':
                    return member.size
    except (tarfile.TarError, OSError):
        return None
    return None


def check_kernel(root, variant):
    """Record the built kernel version; honk additionally needs BPF options."""
    configs = list(root.glob('build_dir/target-*/linux-*/linux-*/.config'))
    if len(configs) != 1:
        if variant == 'honk':
            sys.exit(f'Expected one kernel .config, found {len(configs)}.')
        return {}
    text = configs[0].read_text()
    info = {'kernel_config': str(configs[0].relative_to(root))}
    match = re.search(r'linux-(\d+\.\d+(?:\.\d+)?)', str(configs[0]))
    if match:
        info['kernel_version'] = match.group(1)
    if variant != 'honk':
        return info
    if 'CONFIG_CGROUP_BPF=y' not in text:
        sys.exit('The built kernel has no CONFIG_CGROUP_BPF=y; honk cannot start on it.')
    if 'CONFIG_DEBUG_INFO=y' not in text:
        sys.exit('The built kernel has no CONFIG_DEBUG_INFO=y; the BTF blob would be useless.')
    if 'CONFIG_DEBUG_INFO_REDUCED=y' in text:
        sys.exit('The built kernel uses DEBUG_INFO_REDUCED; pahole cannot produce full BTF.')
    info['cgroup_bpf'] = True
    return info


def check_btf(root):
    blobs = list(root.glob('staging_dir/target-*/root-*/usr/lib/debug/boot/vmlinux'))
    if len(blobs) != 1:
        sys.exit(f'Expected one installed BTF blob, found {len(blobs)}.')
    size = blobs[0].stat().st_size
    if size < 512 * 1024:
        sys.exit(f'The installed BTF blob is only {size} bytes; pahole probably failed.')
    head = blobs[0].read_bytes()[:2]
    if head != b'\x9f\xeb':
        sys.exit('The installed BTF blob does not start with the BTF magic.')
    return size


def collect(root, destination, variant):
    root = pathlib.Path(root).resolve()
    destination = pathlib.Path(destination).resolve()
    spec = variants.VARIANTS[variant]

    payload = json.loads((root / spec['release_json']).read_text())
    installed = list(root.glob(f'staging_dir/target-*/root-*/{spec["binary"]}'))
    if len(installed) != 1:
        sys.exit(f'Expected one installed {spec["payload"]} binary, found {len(installed)}.')
    actual = hashlib.sha256(installed[0].read_bytes()).hexdigest()
    if actual != payload['binary_sha256']:
        sys.exit(f'The root filesystem does not contain the selected {spec["payload"]} binary.')

    kernel = check_kernel(root, variant)
    btf_bytes = check_btf(root) if variant == 'honk' else None

    images_dir = root / 'bin/targets' / variants.IMAGES_DIR
    # The per-device manifest also carries the device name, so exclude it here:
    # `images` is supposed to be the flashable set and ends up in variant.json.
    images = sorted(p for p in images_dir.glob(f'*{variants.DEVICE}*')
                    if p.is_file() and p.suffix != '.manifest')
    sysupgrade = [p for p in images if 'sysupgrade' in p.name and p.suffix == '.bin']
    if not sysupgrade:
        sys.exit('No Tenda BE12 Pro sysupgrade image was produced.')

    sizes = [kernel_size(image) for image in sysupgrade]
    unreadable = [image.name for image, size in zip(sysupgrade, sizes) if size is None]
    if unreadable:
        sys.exit(f'Could not read the kernel size from {", ".join(unreadable)}; '
                 'refusing to publish an unchecked image.')
    measured = max(sizes)
    if measured >= KERNEL_LIMIT:
        sys.exit(f'The kernel is {measured / 1048576:.2f} MB but the partition holds '
                 f'{KERNEL_LIMIT / 1048576:.0f} MB; the image would not boot.')
    if measured > KERNEL_LIMIT * 0.95:
        print(f'warning: the kernel is {measured / 1048576:.2f} MB of '
              f'{KERNEL_LIMIT / 1048576:.0f} MB', file=sys.stderr)

    destination.mkdir(parents=True, exist_ok=True)
    for image in images:
        shutil.copy2(image, destination / image.name)
    manifests = sorted(images_dir.glob(f'*{variants.DEVICE}*.manifest'))
    if not manifests:
        sys.exit('No installed-package manifest was produced for the Release.')
    for manifest in manifests:
        shutil.copy2(manifest, destination / manifest.name)

    shutil.copy2(root / spec['release_json'], destination / f'{spec["payload"]}-release.json')
    shutil.copy2(root / 'source-commit.txt', destination / 'immortalwrt-commit.txt')
    shutil.copy2(root / 'source-metadata.json', destination / 'source-metadata.json')

    record = {
        'variant': variant,
        'title': spec['title'],
        **kernel,
        'payload': spec['payload'],
        'payload_tag': payload['tag'],
        'payload_sha256': payload['binary_sha256'],
        'kernel_bytes': measured,
        'kernel_partition_bytes': KERNEL_LIMIT,
        'btf_bytes': btf_bytes,
        'images': [p.name for p in images],
    }
    (destination / 'variant.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'{variant}: collected {len(images)} device files, '
          f'{spec["payload"]} SHA-256 matches {payload["tag"]}, '
          f'kernel {measured / 1048576:.2f} MB')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit('usage: collect_outputs.py <immortalwrt-root> <destination> <variant>')
    collect(sys.argv[1], sys.argv[2], sys.argv[3])
