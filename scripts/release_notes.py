#!/usr/bin/env python3
"""Generate the Release notes for every variant collected in one directory.

Usage: release_notes.py <release-dir> <output.md>

Normally <release-dir> holds one subdirectory per variant (firmware-passwall/,
firmware-honk/), each with variant.json, source-metadata.json and the payload
release metadata. A single-artifact download may instead flatten the files into
<release-dir> itself; that layout is accepted too.
"""

import json
import pathlib
import sys

ORDER = ('passwall', 'honk')
TITLES = {'passwall': 'Passwall + Xray', 'honk': 'honk（无 Passwall）'}


def load(release_dir):
    flat_variant = None
    flat_record = release_dir / 'variant.json'
    if flat_record.is_file():
        try:
            flat_variant = json.loads(flat_record.read_text()).get('variant')
        except json.JSONDecodeError:
            pass

    found = {}
    for variant in ORDER:
        candidates = [release_dir / f'firmware-{variant}', release_dir / variant]
        if flat_variant == variant:
            candidates.insert(0, release_dir)
        directory = next((p for p in candidates if (p / 'variant.json').is_file()), None)
        if directory is None:
            continue
        record = json.loads((directory / 'variant.json').read_text())
        payload = json.loads((directory / f'{record["payload"]}-release.json').read_text())
        found[variant] = {
            'variant': record,
            'source': json.loads((directory / 'source-metadata.json').read_text()),
            'payload': payload,
        }
    if not found:
        sys.exit(f'no variant metadata under {release_dir}')
    return found


def overview(found):
    lines = ['| 变体 | 代理组件 | 版本 | 内核占用 | 文件前缀 |', '| --- | --- | --- | --- | --- |']
    for variant, data in found.items():
        payload = data['payload']
        project = payload.get('project', 'XTLS/Xray-core')
        kernel = data['variant'].get('kernel_bytes')
        kernel_text = f'{kernel / 1048576:.2f} MB / 6 MB' if kernel else '—'
        lines.append(f'| {TITLES[variant]} | {project} | `{payload["tag"]}` | {kernel_text} | `{variant}-` |')
    return lines


def variant_section(variant, data):
    source, record, payload = data['source'], data['variant'], data['payload']
    lines = [f'## {TITLES[variant]}', '']
    lines.append(f'- ImmortalWrt：`{source["immortalwrt_branch"]}` @ `{source["immortalwrt_commit"]}`')
    lines.append(f'- 配置 SHA-256：`{source["input_config_sha256"]}`')
    version = record.get('kernel_version')
    if version:
        lines.append(f'- 内核版本：`{version}`')
    if variant == 'passwall':
        lines.append(f'- Passwall feed 版本：`{source["passwall_version"]}`')
        lines.append(f'- Xray 官方版本：`{payload["tag"]}`'
                     + ('（预发布版）' if payload.get('prerelease') else ''))
        lines.append('- Xray 版本策略：按发布时间取最新的已发布版本（含 beta/rc），不是最新正式版。')
        lines.append('- 官方 Xray 二进制已替换 feed 里源码编译的版本，构建时校验了发布页 SHA-256。')
    else:
        lines.append(f'- honk 版本：`{payload["tag"]}`'
                     + ('（上游预发布版）' if payload.get('prerelease') else ''))
        lines.append(f'- 官方二进制：`{payload["asset"]}`，{payload["binary_size"] / 1048576:.1f} MB，'
                     'SHA-256 已与上游 SHA256SUMS 核对。')
        lines.append('- 内核：`CONFIG_KERNEL_CGROUP_BPF=y`（honk 数据面必需）随配置启用，'
                     '`DEBUG_INFO_REDUCED` 已关以便生成 BTF；其余内核选项未改动。')
        btf = record.get('btf_bytes')
        if btf:
            lines.append(f'- BTF：`/usr/lib/debug/boot/vmlinux`（{btf / 1048576:.1f} MB），'
                         '由本次内核的 vmlinux 现场生成，未塞进仅 6 MB 的内核分区。')
        lines.append('- 服务**默认关闭**：先 `/etc/init.d/honk enable && start`，'
                     '或直接编辑 `/etc/honk/config.dae` 后重启。')
        lines.append('- 面板：`http://<路由器 LAN IP>:9527/`（内嵌 doona，首次访问创建管理员）。')
        lines.append('- 不含 Passwall/Xray/haproxy/shadowsocks-rust 等上一版代理栈。')
    kernel = record.get('kernel_bytes')
    if kernel:
        lines.append(f'- 内核镜像 {kernel / 1048576:.2f} MB / 分区 6.00 MB。')
    return lines


def source_section(found):
    """Each matrix job clones master independently, so list them separately."""
    lines = ['## 源码与 feed', '']
    for variant, data in found.items():
        lines.append(f'### {TITLES[variant]}')
        lines.append('')
        for name, feed in data['source']['feeds'].items():
            lines.append(f'- {name}：`{feed["branch"]}` @ `{feed["commit"]}`')
        lines.append('')
    return lines


def main(release_dir, output):
    release_dir = pathlib.Path(release_dir)
    found = load(release_dir)
    first = next(iter(found.values()))['source']

    if len(found) == 2:
        summary = ('- 本次发布包含两套互斥固件，文件名分别以 `passwall-` 和 `honk-` 开头，'
                   '刷机时任选其一。')
    else:
        only = next(iter(found))
        summary = (f'- 本次发布只包含 **{only}** 一个变体（另一变体本次构建失败），'
                   f'附件文件名以 `{only}-` 开头。')

    lines = [
        '# Tenda BE12 Pro ImmortalWrt 固件',
        '',
        f'- ImmortalWrt 分支：`{first["immortalwrt_branch"]}`',
        summary,
        '',
        '## 版本速览',
        '',
    ]
    lines += overview(found)
    lines.append('')
    for variant, data in found.items():
        lines += variant_section(variant, data)
        lines.append('')

    lines += source_section(found)
    lines += [
        '插件版本来自上述提交；独立上游项目可能已有尚未进入 ImmortalWrt 的更新。',
        '附件中的 `.manifest` 列出实际安装的软件包版本，`source-metadata.json` 记录完整提交，',
        '`SHA256SUMS` 用于校验全部附件。',
        '',
        '## 刷机注意',
        '',
        '- 仅适用于 Tenda BE12 Pro（mt7987a，mediatek/filogic），请勿刷到其他机型。',
        '- 内核分区只有 6 MB，流水线会在内核超出分区时直接失败，不会产出无法启动的镜像。',
    ]
    versions = sorted({d['variant'].get('kernel_version') for d in found.values()
                       if d['variant'].get('kernel_version')})
    kernel_note = ('、'.join(versions) if versions else '本次 ImmortalWrt master 构建的内核')
    lines.append(f'- honk 版要求内核 6.12 以上：本次内核为 {kernel_note}；'
                 '回退到更老的官方固件后 honk 将无法启动。')

    drift = [note for data in found.values()
             for note in data['source'].get('drift_notes', [])]
    if drift:
        lines += ['', '## 构建期间的源码漂移', '']
        lines += [f'- {note}' for note in drift]
    output = pathlib.Path(output)
    output.write_text('\n'.join(lines) + '\n')
    print(f'wrote {output}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: release_notes.py <release-dir> <output.md>')
    main(sys.argv[1], sys.argv[2])
