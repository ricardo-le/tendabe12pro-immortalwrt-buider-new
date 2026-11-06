#!/usr/bin/env python3
"""Record and verify the upstream source revisions used by this build.

A feed that moves between `feeds update` and this check used to abort the
whole build. Drifting feeds are common and harmless as long as the revision
that was actually used is recorded, so drift is a warning now.
"""

import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args],
                                   text=True, stderr=subprocess.DEVNULL).strip()


def remote_head(path):
    try:
        return git(path, 'ls-remote', 'origin', 'HEAD').split()[0]
    except (subprocess.CalledProcessError, IndexError):
        return ''


def revision(path, label, notes):
    local = git(path, 'rev-parse', 'HEAD')
    remote = remote_head(path)
    if remote and remote != local:
        notes.append(f'{label}: built {local}, remote HEAD moved to {remote}')
    return {'branch': git(path, 'rev-parse', '--abbrev-ref', 'HEAD'), 'commit': local}


def record(root, config_path, variant):
    root = pathlib.Path(root).resolve()
    config_path = pathlib.Path(config_path).resolve()
    notes = []

    branch = git(root, 'symbolic-ref', '--short', 'HEAD')
    if branch != 'master':
        sys.exit(f'Expected ImmortalWrt master, found {branch}.')
    source = revision(root, 'immortalwrt', notes)

    feeds = {}
    for path in sorted((root / 'feeds').iterdir()):
        if (path / '.git').exists():
            feeds[path.name] = revision(path, f'feeds/{path.name}', notes)

    metadata = {
        'variant': variant,
        'immortalwrt_branch': source['branch'],
        'immortalwrt_commit': source['commit'],
        'input_config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'feeds': feeds,
        'drift_notes': notes,
    }

    if variant == 'passwall':
        makefile = root / 'feeds/luci/applications/luci-app-passwall/Makefile'
        match = re.search(r'^PKG_VERSION:=([^\s]+)$', makefile.read_text(), re.MULTILINE)
        if not match:
            sys.exit('Could not read the Passwall version from the luci feed.')
        metadata['passwall_version'] = match.group(1)
    else:
        payload = json.loads((root / 'honk-prebuilt/release.json').read_text())
        metadata['honk'] = {key: payload[key] for key in
                            ('tag', 'package_version', 'asset', 'prerelease',
                             'archive_sha256', 'binary_sha256', 'binary_size')}

    (root / 'source-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (root / 'source-commit.txt').write_text(source['commit'] + '\n')
    for note in notes:
        print(f'warning: {note}', file=sys.stderr)
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit('usage: record_sources.py <immortalwrt-root> <config> <passwall|honk>')
    record(sys.argv[1], sys.argv[2], sys.argv[3])
