#!/usr/bin/env python3
"""Generate traceable GitHub Release notes from the verified build metadata."""

import json
import pathlib
import sys

assets = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
source = json.loads((assets / 'source-metadata.json').read_text())
xray = json.loads((assets / 'xray-release.json').read_text())
lines = [
    '# Tenda BE12 Pro ImmortalWrt 固件',
    '',
    f'- ImmortalWrt 分支：`{source["immortalwrt_branch"]}`',
    f'- ImmortalWrt 提交：`{source["immortalwrt_commit"]}`',
    f'- 原始配置 SHA-256：`{source["input_config_sha256"]}`',
    f'- Passwall feed 版本：`{source["passwall_version"]}`',
    f'- Xray 官方版本：`{xray["tag"]}`' + ('（预发布版）' if xray['prerelease'] else ''),
    '',
    '## Feed 提交',
    '',
]
lines += [f'- {name} 分支：`{feed["branch"]}`，提交：`{feed["commit"]}`'
          for name, feed in source['feeds'].items()]
lines += [
    '',
    '编译前已核对源码和 feeds 与各自远端 HEAD 一致。',
    '插件版本来自这些提交；独立上游项目可能已有尚未进入 ImmortalWrt 的更新。',
    '附件中的 `.manifest` 列出实际安装的软件包版本；`source-metadata.json` 记录完整提交；`SHA256SUMS` 用于校验文件。',
    '',
    '请仅刷入与 Tenda BE12 Pro 及当前启动布局匹配的镜像。',
]
output.write_text('\n'.join(lines) + '\n')
