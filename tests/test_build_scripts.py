"""Offline regressions for config preparation and firmware publication."""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import check_config
import collect_outputs
import derive_honk_config
import fetch_luci
import release_notes
import stage_release
import variants


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def quiet(self):
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return stack


class ConfigTests(Workspace):
    def test_committed_honk_snapshot_matches_base_config(self):
        target = self.root / 'honk.config'
        with self.quiet():
            derive_honk_config.main(REPO / 'tendabe12pro.config', target)
        self.assertEqual(target.read_bytes(), (REPO / 'tendabe12pro-honk.config').read_bytes())

    def test_derivation_overrides_disabled_packages_without_duplicate_symbols(self):
        source = self.root / 'source.config'
        target = self.root / 'honk.config'
        source.write_text('# CONFIG_PACKAGE_kmod-veth is not set\n'
                          'CONFIG_PACKAGE_luci-app-honk=m\n'
                          'CONFIG_PACKAGE_xray-core=y\n')
        with self.quiet():
            derive_honk_config.main(source, target)
        lines = target.read_text().splitlines()
        self.assertIn('CONFIG_PACKAGE_kmod-veth=y', lines)
        self.assertIn('CONFIG_PACKAGE_luci-app-honk=y', lines)
        self.assertNotIn('# CONFIG_PACKAGE_kmod-veth is not set', lines)
        self.assertNotIn('CONFIG_PACKAGE_luci-app-honk=m', lines)
        self.assertIn('# CONFIG_PACKAGE_xray-core is not set', lines)

    def test_derivation_enables_honk_kernel_prerequisites(self):
        source, target = self.root / 'source', self.root / 'target'
        source.write_text('# CONFIG_KERNEL_DEBUG_INFO is not set\n'
                          '# CONFIG_KERNEL_CGROUPS is not set\n'
                          '# CONFIG_KERNEL_CGROUP_BPF is not set\n'
                          'CONFIG_KERNEL_DEBUG_INFO_REDUCED=y\n'
                          'CONFIG_KERNEL_DEBUG_INFO_BTF=y\n')
        with self.quiet():
            derive_honk_config.main(source, target)
        lines = target.read_text().splitlines()
        for line in ('CONFIG_KERNEL_DEBUG_INFO=y', 'CONFIG_KERNEL_CGROUPS=y',
                     'CONFIG_KERNEL_CGROUP_BPF=y',
                     '# CONFIG_KERNEL_DEBUG_INFO_REDUCED is not set',
                     '# CONFIG_KERNEL_DEBUG_INFO_BTF is not set'):
            self.assertIn(line, lines)

    def test_passwall_rejects_honk_payload(self):
        config = self.root / '.config'
        config.write_text('\n'.join(variants.VARIANTS['passwall']['required']) +
                          '\nCONFIG_PACKAGE_honk=y\n')
        with self.quiet(), self.assertRaises(SystemExit):
            check_config.check(config, 'passwall')


class ImageTests(Workspace):
    KERNEL_OPTIONS = '''CONFIG_BPF=y
CONFIG_BPF_SYSCALL=y
CONFIG_BPF_JIT=y
CONFIG_CGROUP_BPF=y
CONFIG_NET_SCHED=y
CONFIG_NET_CLS_ACT=y
CONFIG_NET_XGRESS=y
CONFIG_NET_NS=y
CONFIG_NF_TABLES=m
CONFIG_NF_TABLES_INET=y
CONFIG_NFT_CT=m
CONFIG_NFT_QUEUE=m
CONFIG_NETFILTER_NETLINK_QUEUE=m
CONFIG_DEBUG_INFO=y
'''

    def kernel_config(self, text, version='6.18.60'):
        path = self.root / f'build_dir/target-aarch64/linux-mediatek_filogic/linux-{version}/.config'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_honk_kernel_accepts_module_dependencies(self):
        self.kernel_config(self.KERNEL_OPTIONS)
        info = collect_outputs.check_kernel(self.root, 'honk')
        self.assertEqual(info['kernel_version'], '6.18.60')
        self.assertTrue(info['cgroup_bpf'])

    def test_honk_kernel_rejects_missing_datapath_capability(self):
        self.kernel_config(self.KERNEL_OPTIONS.replace('CONFIG_NET_XGRESS=y\n', ''))
        with self.quiet(), self.assertRaises(SystemExit):
            collect_outputs.check_kernel(self.root, 'honk')

    def test_honk_kernel_rejects_unsupported_version(self):
        self.kernel_config(self.KERNEL_OPTIONS, version='6.6.100')
        with self.quiet(), self.assertRaises(SystemExit):
            collect_outputs.check_kernel(self.root, 'honk')

    def image(self, members):
        path = self.root / 'sysupgrade.bin'
        with tarfile.open(path, 'w') as archive:
            for name, data, kind in members:
                entry = tarfile.TarInfo('sysupgrade-tenda_be12-pro/' + name)
                entry.type = kind
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
        return path

    def test_valid_sysupgrade_kernel(self):
        path = self.image([('kernel', b'kernel', tarfile.REGTYPE),
                           ('root', b'rootfs', tarfile.REGTYPE)])
        self.assertEqual(collect_outputs.kernel_size(path), 6)

    def test_rejects_empty_duplicate_or_nonregular_kernel(self):
        for members in (
            [('kernel', b'', tarfile.REGTYPE), ('root', b'root', tarfile.REGTYPE)],
            [('kernel', b'x', tarfile.REGTYPE), ('kernel', b'x', tarfile.REGTYPE),
             ('root', b'root', tarfile.REGTYPE)],
            [('kernel', b'', tarfile.SYMTYPE), ('root', b'root', tarfile.REGTYPE)],
            [('kernel', b'x', tarfile.REGTYPE)],
        ):
            with self.subTest(members=members):
                self.assertIsNone(collect_outputs.kernel_size(self.image(members)))

    def test_installed_manifest_checks_variant_packages(self):
        manifest = self.root / 'device.manifest'
        # A valid honk manifest must not contain Xray even if .config was clean.
        names = ['honk', 'luci-app-honk', 'luci-lib-daeuniverse',
                 'vmlinux-btf-local', 'kmod-veth', 'kmod-nft-queue',
                 'kmod-nfnetlink-queue', 'kmod-sched-bpf', 'kmod-sched-core',
                 'v2ray-geoip', 'v2ray-geosite', 'openssh-sftp-server']
        manifest.write_text(''.join(f'{name} - 1-r1\n' for name in names))
        collect_outputs.check_manifest(manifest, 'honk')
        manifest.write_text(manifest.read_text() + 'xray-core - 1-r1\n')
        with self.quiet(), self.assertRaises(SystemExit):
            collect_outputs.check_manifest(manifest, 'honk')
        manifest.write_text('honk - 1-r1\n')
        with self.quiet(), self.assertRaises(SystemExit):
            collect_outputs.check_manifest(manifest, 'honk')


class CollectTests(Workspace):
    def buildroot(self, kernel_bytes):
        prebuilt = self.root / 'xray-prebuilt'
        prebuilt.mkdir(exist_ok=True)
        (prebuilt / 'release.json').write_text(json.dumps({
            'tag': 'v1', 'binary_sha256': hashlib.sha256(b'xray').hexdigest()}))
        binary = self.root / 'staging_dir/target-aarch64/root-mediatek/usr/bin/xray'
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b'xray')
        images = self.root / 'bin/targets/mediatek/filogic'
        images.mkdir(parents=True, exist_ok=True)
        image = images / 'immortalwrt-tenda_be12-pro-sysupgrade.bin'
        with tarfile.open(image, 'w') as archive:
            for name, data in [('kernel', b'k' * kernel_bytes), ('root', b'rootfs')]:
                member = tarfile.TarInfo('sysupgrade-tenda_be12-pro/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        (images / 'immortalwrt-tenda_be12-pro.manifest').write_text(
            'luci-app-passwall - 1-r1\nxray-core - 1-r1\nopenssh-sftp-server - 1-r1\n')
        (self.root / 'source-commit.txt').write_text('abc\n')
        (self.root / 'source-metadata.json').write_text('{"variant":"passwall"}\n')
        return image

    def test_kernel_exactly_fits_partition(self):
        image = self.buildroot(6 * 1024 * 1024)
        with self.quiet():
            collect_outputs.collect(self.root, self.root / 'output', 'passwall')
        self.assertTrue((self.root / 'output' / image.name).is_file())

    def test_kernel_overflow_is_not_collected(self):
        self.buildroot(6 * 1024 * 1024 + 1)
        with self.quiet(), self.assertRaises(SystemExit):
            collect_outputs.collect(self.root, self.root / 'output', 'passwall')
        self.assertFalse((self.root / 'output').exists())


class ReleaseTests(Workspace):
    def artifact(self, variant='passwall', flat=False):
        directory = self.root / 'release'
        if not flat:
            directory /= 'firmware-' + variant
        directory.mkdir(parents=True, exist_ok=True)
        payload = 'xray' if variant == 'passwall' else 'honk'
        image = 'immortalwrt-tenda_be12-pro-sysupgrade.bin'
        record = {'variant': variant, 'payload': payload, 'images': [image]}
        source = {'variant': variant, 'immortalwrt_branch': 'master',
                  'immortalwrt_commit': 'abc', 'input_config_sha256': '123',
                  'passwall_version': '1', 'feeds': {}}
        for name, data in [('variant.json', record), ('source-metadata.json', source),
                           (payload + '-release.json', {'tag': 'v1', 'asset': 'asset',
                                                       'binary_size': 1024})]:
            (directory / name).write_text(json.dumps(data))
        (directory / image).write_bytes(b'firmware')
        (directory / 'immortalwrt-commit.txt').write_text('abc\n')
        (directory / 'device.manifest').write_text(payload + ' - 1-r1\n')
        return directory, image

    def test_complete_variant_has_prefixed_assets_and_correct_checksums(self):
        directory, image = self.artifact()
        with self.quiet():
            stage_release.main(self.root / 'release', self.root / 'upload')
        self.assertEqual((self.root / 'upload' / ('passwall-' + image)).read_bytes(), b'firmware')
        for line in (self.root / 'upload/SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ')
            self.assertEqual(digest, hashlib.sha256((self.root / 'upload' / name).read_bytes()).hexdigest())
        self.assertEqual(list(release_notes.load(self.root / 'release')), ['passwall'])

    def test_partial_download_is_not_published_or_listed_in_notes(self):
        self.artifact()
        directory, image = self.artifact('honk')
        (directory / image).unlink()
        with self.quiet():
            stage_release.main(self.root / 'release', self.root / 'upload')
            notes = release_notes.load(self.root / 'release')
        self.assertEqual(list(notes), ['passwall'])
        self.assertFalse(any(p.name.startswith('honk-') for p in (self.root / 'upload').iterdir()))

    def test_mislabelled_artifact_is_not_published(self):
        directory, _ = self.artifact()
        record = json.loads((directory / 'variant.json').read_text())
        record['variant'] = 'honk'
        (directory / 'variant.json').write_text(json.dumps(record))
        with self.quiet(), self.assertRaises(SystemExit):
            stage_release.main(self.root / 'release', self.root / 'upload')

    def test_single_flat_download_still_works(self):
        self.artifact(flat=True)
        with self.quiet():
            stage_release.main(self.root / 'release', self.root / 'upload')
        self.assertEqual(list(release_notes.load(self.root / 'release')), ['passwall'])

    def test_empty_downloads_fail(self):
        (self.root / 'release').mkdir()
        with self.quiet(), self.assertRaises(SystemExit):
            stage_release.main(self.root / 'release', self.root / 'upload')


class LuciTests(Workspace):
    def test_staging_into_source_repository_is_rejected(self):
        # Before any download/deletion, catch accidental use of the builder
        # itself as the buildroot. The vendored files must survive unchanged.
        source = self.root / 'package/luci-app-honk/Makefile'
        for name in fetch_luci.PACKAGES:
            shutil.copytree(REPO / 'package' / name, self.root / 'package' / name)
        baseline = source.read_text()
        with mock.patch.object(fetch_luci, '_stage_upstream', side_effect=RuntimeError('offline')):
            with self.quiet(), self.assertRaises((SystemExit, ValueError)):
                fetch_luci.stage(self.root, self.root)
        self.assertTrue(source.is_file())
        self.assertEqual(source.read_text(), baseline)

    def test_explicit_pin_does_not_silently_fall_back(self):
        with mock.patch.object(fetch_luci, '_stage_upstream', side_effect=RuntimeError('no such ref')):
            with self.quiet(), self.assertRaises((RuntimeError, SystemExit)):
                fetch_luci.stage(self.root, REPO, ref='missing-pinned-commit')
        self.assertFalse((self.root / 'luci-apps.json').exists())

    def test_default_fallback_replaces_stale_files(self):
        stale = self.root / 'package/luci-app-honk/stale.js'
        stale.parent.mkdir(parents=True)
        stale.write_text('stale upstream file')
        with mock.patch.object(fetch_luci, '_stage_upstream', side_effect=RuntimeError('offline')):
            with self.quiet(), mock.patch.dict('os.environ', {}, clear=True):
                result = fetch_luci.stage(self.root, REPO)
        self.assertEqual(result['source'], 'vendored')
        self.assertFalse(stale.exists())
        helper = self.root / 'package/luci-lib-daeuniverse/root/usr/libexec/daeuniverse-pkg'
        self.assertTrue(helper.stat().st_mode & 0o111)


if __name__ == '__main__':
    unittest.main()
