# tendabe12pro-immortalwrt-buider-new

Tenda BE12 Pro（mt7987a / mediatek-filogic）的 ImmortalWrt 固件，用 GitHub Actions 云端编译，
**一次运行产出两个互斥变体**，放在同一个 Release 里。

| 变体 | 代理组件 | 说明 | 文件前缀 |
| --- | --- | --- | --- |
| `passwall` | Passwall + 官方最新 Xray 内核 | 原有固件，行为不变 | `passwall-` |
| `honk` | [daeuniverse/honk](https://github.com/daeuniverse/honk) | **完全不含 Passwall 全家桶**（也不含 Xray），带内嵌 doona 面板 | `honk-` |

两个变体在**各自的 runner** 上拉取同一时间点的 ImmortalWrt master 与 feeds（不保证完全
相同的提交，Release 说明按变体分别列出实际 commit），只是包选择和内核选项不同。
两个变体的配置里都**默认不装 AdGuardHome**（`adguardhome` 与 `luci-app-adguardhome`），
但流水线**不拦它**——想要就自己在 `menuconfig` 里勾回来，`check_config.py` 不会因此报错。

## 目录结构

```
.github/workflows/build.yml     # matrix 构建两个变体 + 汇总发布
tendabe12pro.config             # passwall 变体配置（基准配置，menuconfig 维护）
tendabe12pro-honk.config        # honk 变体配置（由脚本派生，勿手改）
package/honk/                   # honk 本地包：预编译 honk-core + 首启脚本 + 默认配置
package/vmlinux-btf-local/      # 把本次内核的 BTF 装进 rootfs（不占 6MB 内核分区）
scripts/prepare.py              # 变体准备总入口（CI 调它）
scripts/prepare_xray.py         # 替换 feed 里源码编译的 Xray 为官方二进制
scripts/prepare_honk.py         # 下载校验 honk 最新发布、铺设本地包
scripts/derive_honk_config.py   # 从基准配置派生 honk 版配置
scripts/check_config.py         # 校验 defconfig 没丢设备/包，且没混入对方包
scripts/record_sources.py       # 记录实际使用的源码与 feed 提交
scripts/collect_outputs.py      # 校验产物、量内核体积、收集镜像
scripts/stage_release.py        # 加变体前缀、生成总校验和
scripts/release_notes.py        # 生成双变体 Release 说明
```

## 触发构建

- 手动：Actions → **Build Tenda BE12 Pro ImmortalWrt** → Run workflow。
  可选填 `honk_tag`（例如 `v0.1.0-beta.6`）固定版本；留空则自动取上游
  **按发布时间最新的已发布版本**。
- 定时：每周一、三、五 02:00（北京时间）。

**Xray 版本策略（刻意需求，别改）**：passwall 版用的是 Xray 官方**按发布时间最新的
已发布版本，包含 beta/rc 预发布版**，不是"最新正式版"。只跳过 draft 和缺少
`Xray-linux-arm64-v8a.zip` 资产的发布。是否为预发布会在 Release 说明里标注。
honk 版同样自动取上游最新已发布版本（上游目前全是 beta，故不存在"只取正式版"的选项）；
只认 `vX.Y.Z…` 形式的 tag 且必须带 `honk-core-<tag>-aarch64-unknown-linux-musl-full.tar.gz`，
上游的 `debug` / `debug-diag.*` 调试发布会因此被跳过。想复现旧版本就手填 `honk_tag`。

两个变体并行跑，任何一个失败都不会影响另一个的产物发布；Release 说明里只会列出成功的变体，
并分别标注各自的源码提交与 feed 提交。

## 产物

Release 里所有附件都带变体前缀，例如：

```
passwall-immortalwrt-mediatek-filogic-tenda_be12-pro-squashfs-sysupgrade.bin
honk-immortalwrt-mediatek-filogic-tenda_be12-pro-squashfs-sysupgrade.bin
passwall-…initramfs-kernel.bin / honk-…initramfs-kernel.bin   # 恢复用
passwall-…manifest / honk-…manifest                          # 实际安装的包清单
passwall-immortalwrt-commit.txt / honk-immortalwrt-commit.txt
passwall-source-metadata.json / honk-source-metadata.json
passwall-variant.json / honk-variant.json
passwall-xray-release.json / honk-release.json               # 上游二进制来源
SHA256SUMS
```

刷机时任选一个变体，不要混刷。`SHA256SUMS` 覆盖全部附件。

## 只在编译机上出配置，不本地编译

基准配置 `tendabe12pro.config` 是唯一需要 menuconfig 维护的文件；honk 版配置由脚本派生，
这样两份配置不会各自漂移：

```sh
git clone --depth=1 -b master https://github.com/immortalwrt/immortalwrt.git immortalwrt
cd immortalwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cp ../tendabe12pro.config .config
make menuconfig                 # 改完保存
cp .config ../tendabe12pro.config

cd .. && python3 scripts/derive_honk_config.py
```

`derive_honk_config.py` 会做三件事，并打印逐条 diff：

1. 删掉整个 Passwall 栈：`luci-app-passwall*`、中文语言包，以及 `haproxy`、
   `shadowsocks-rust-*`、`simple-obfs-client`、`v2ray-plugin`、`geoview`、`chinadns-ng`、
   `dns2socks`、`microsocks`、`xray-core`；
2. 关掉 `CONFIG_KERNEL_DEBUG_INFO_REDUCED`（pahole 需要完整 DWARF 才能生成 BTF）；
3. 加上 `honk`、`vmlinux-btf-local`、`kmod-veth`、`kmod-nft-queue`、
   `kmod-nfnetlink-queue`、`v2ray-geoip`、`v2ray-geosite`。

honk 需要的 `CONFIG_CGROUP_BPF` 通过 `CONFIG_KERNEL_CGROUP_BPF=y` 打开，不需要改
target 的内核配置文件：OpenWrt 的 `Kernel/Configure/Default` 会用 awk 把 `.config`
里的 `CONFIG_KERNEL_*` 去掉前缀后复制进内核 `.config`。流水线在编译完成后再从内核
`.config` 里核对一次，确保它真的是 `=y`。

## honk 版说明

- **服务默认关闭**。刷完先改 `/etc/honk/config.dae`，再
  `/etc/init.d/honk enable && /etc/init.d/honk start`。
- 面板：`http://<路由器 LAN IP>:9527/`（内嵌 doona，首次访问创建管理员，
  默认只走 HTTP，防火墙默认不放行 WAN）。
- 配置文件 `/etc/honk/config.dae`，UCI 只有 `honk.config.config_file` 一项。
- 运行时要求：内核 6.12+（实际版本由 ImmortalWrt master 决定，见 Release 说明里
  的 `kernel_version`）、cgroup v2、bpffs、内核 BTF。首启脚本会自动挂 bpffs 与 cgroup2。
- honk 目前只有 `v0.1.0-beta.x`，上游全部标为预发布、明确不建议生产使用；
  首次部署请保留带外管理通道（串口/SSH 兜底）。
- 二进制是官方静态 musl aarch64 `full` 构建（Clash API + 原生 API + 内嵌 doona），
  约 29.5 MB，全部落在 rootfs（约 90 MB 的 ubi 分区）。

### 为什么不把 BTF 编进内核

内核分区只有 6 MB，现有内核已占 4.56 MB。塞 `.BTF` 段极可能溢出导致无法启动，
所以 `vmlinux-btf-local` 在构建时用 pahole 从本次内核的 `vmlinux` 提取 BTF，
装到 `/usr/lib/debug/boot/vmlinux`（honk 会查这个路径），体积落在 rootfs 里。
代价是内核要用完整 DWARF 编译（`DEBUG_INFO_REDUCED` 关闭），构建时间和磁盘占用略增。

**pahole 必须 ≥ 1.24**：GCC 14 编译的 6.12+ 内核会产出 `DW_TAG_unspecified_type`，
1.22 及更早版本直接报 `Unsupported DW_TAG_unspecified_type` 中断。CI 里从源码编译
dwarves v1.32 并装到 `/usr/local/bin`，不依赖发行版版本（Ubuntu 24.04 自带 1.25 恰好可用，
Debian 11 自带 1.22 不可用）。本地编译同样需要：

```sh
git clone --depth=1 -b v1.32 https://github.com/acmel/dwarves.git
cmake -S dwarves -B dwarves/build -DCMAKE_BUILD_TYPE=Release
cmake --build dwarves/build -j"$(nproc)" && sudo cmake --install dwarves/build
```

## 流水线里的硬性检查

任何一项不过，构建直接失败，不会产出可疑镜像：

- `check_config.py`：设备 profile 在、变体包在、**对方变体的包不在**（AdGuardHome 不拦）；
- Xray：按发布时间取最新的已发布版本（**含 beta/rc**，见上文版本策略），跳过 draft
  与缺少 arm64 资产的发布；校验发布页 SHA-256、ELF 为 aarch64，并核对 rootfs 里的二进制哈希；
- honk：校验发布页 SHA-256 与 `SHA256SUMS` 双重一致、ELF 为 aarch64，
  核对 rootfs 里的 `honk-core` 哈希；
- 内核（仅 honk）：`CONFIG_CGROUP_BPF=y`、`CONFIG_DEBUG_INFO=y`、
  `DEBUG_INFO_REDUCED` 已关；
- BTF：magic 为 `9feb` 且不小于 512 KB；
- 内核体积：逐一读取每个 sysupgrade 镜像里 `kernel` 成员，超过 6 MB 分区直接失败，
  超过 95% 告警；**读不出内核尺寸也直接失败**，不会静默跳过；
- feeds 漂移只告警不中断（原实现会因为 feed 恰好更新而随机失败）。

## 已知限制

- 每次运行 2 个变体 × 约 1.5–2 小时；定时每周 3 次，等于每周 6 次构建。想省额度就删掉
  `schedule`，只留手动触发。
- honk 会自动跟进上游最新发布；若 GitHub API 在 CI 里不可用（限流/故障），
  退回 `DEFAULT_TAG` 并打 warning。要固定版本就填 `honk_tag`。
- honk 版不含任何 Passwall 组件，Passwall 的节点订阅/分流规则不能直接迁移，
  需要按 dae 语法重写 `config.dae`。
