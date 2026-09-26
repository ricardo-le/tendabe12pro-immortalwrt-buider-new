#!/usr/bin/env python3
"""Record and verify the upstream source revisions used by this build."""

import hashlib
import json
import pathlib
import re
import subprocess
import sys


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def current_remote_head(path):
    output = git(path, 'ls-remote', 'origin', 'HEAD')
    return output.split()[0]


def verified_commit(path):
    local = git(path, 'rev-parse', 'HEAD')
    remote = current_remote_head(path)
    if local != remote:
        sys.exit(f'{path}: local {local} is behind remote HEAD {remote}; retry the build.')
    return local


def main(root, input_config):
    branch = git(root, 'symbolic-ref', '--short', 'HEAD')
    if branch != 'master':
        sys.exit(f'Expected ImmortalWrt master, found {branch}.')
    source_commit = verified_commit(root)
    feeds = {}
    for name in ('packages', 'luci', 'routing', 'telephony', 'video'):
        path = root / 'feeds' / name
        feeds[name] = {'branch': git(path, 'rev-parse', '--abbrev-ref', 'HEAD'),
                       'commit': verified_commit(path)}

    passwall_makefile = root / 'feeds/luci/applications/luci-app-passwall/Makefile'
    match = re.search(r'^PKG_VERSION:=([^\s]+)$', passwall_makefile.read_text(), re.MULTILINE)
    if not match:
        sys.exit('Could not read the Passwall version from the luci feed.')
    metadata = {'immortalwrt_branch': branch, 'immortalwrt_commit': source_commit,
                'input_config_sha256': hashlib.sha256(input_config.read_bytes()).hexdigest(),
                'feeds': feeds, 'passwall_version': match.group(1)}
    (root / 'source-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (root / 'source-commit.txt').write_text(source_commit + '\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve())
