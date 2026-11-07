# honk 的基线与本项目适配

2026-11-06 核对结论：**OpenWrt 集成以 `daeuniverse/openwrt-packages` 为基线；
代理核心以 `daeuniverse/honk` 的已发布版本为来源。**

这两个仓库负责不同层次。honk 的 README 也将 OpenWrt 用户引向 daeuniverse
软件源。本项目继续通过官方 release 获取核心二进制，以 OpenWrt 包的服务约定
对照本地集成，不将整个第三方 feed 加入 ImmortalWrt。

| 部分 | 基线/来源 | 本项目的做法 |
| --- | --- | --- |
| 核心与内嵌 doona | `daeuniverse/honk` 的最新有效发布 | 下载 aarch64 musl full，校验 SHA-256、ELF 和最终 rootfs 二进制；忽略 debug 标签 |
| procd、UCI、默认配置、依赖 | `daeuniverse/openwrt-packages` | 仓库内维护已审查的本地适配，随固件代码提交一起版本化 |
| LuCI | `daeuniverse/openwrt-packages` | 默认跟随 main 并记录实际 commit；网络失败回退基线；显式指定版本失败则中止 |
| 内核 BTF | 本次 ImmortalWrt 的 `vmlinux` | 用完整 DWARF 提取 detached BTF，存 rootfs，避免占用 6 MiB 内核分区 |

## 核对过的具体版本

- OpenWrt 集成和 LuCI 基线：
  [`e48b222f239e2572244c8cf495fbce79b0da7528`](https://github.com/daeuniverse/openwrt-packages/tree/e48b222f239e2572244c8cf495fbce79b0da7528)。
  本地两个 LuCI 包与该提交逐文件比较一致。
- 当时最新有效核心发布：
  [`v0.1.0-beta.5`](https://github.com/daeuniverse/honk/releases/tag/v0.1.0-beta.5)，
  源码提交 `88d470c662e0ee7a3de3e67afc6129f67e66c1bf`。
  官方 musl full 资产已实际下载并通过项目的校验流程。
- honk main 当时为 `9e31cc0bd28825afdc0e384dc989bc3f076e69cf`，已领先发布版。
  main 的构建特性也有变化；运行时要求和特性核对采用所选 release 的文档及代码。
  日常构建仍按发布时间选择最新有效 release，具体版本见每次发布的元数据。

## 为什么不直接采用整个 OpenWrt feed

1. **内核不同。** 上游 `vmlinux-btf` 包的 `EXTRA_DEPENDS` 要求 SDK 对应的精确
   kernel 版本、vermagic 和 release。官方 OpenWrt SDK 生成的 BTF 不能当作本项目
   ImmortalWrt master 自编译内核的 BTF。
2. **此处关闭了内核内嵌 BTF。** 上游的 `vmlinux-btf-builtin` 假定
   `/sys/kernel/btf/vmlinux` 存在；本机只有 6 MiB 内核分区，采用单独 BTF 文件。
   不能直接用空的 builtin 包来满足运行条件。
3. **构建输入不同。** 上游 honk Makefile 需要额外检出的 `honk/src`、Rust 稳定版和
   eBPF nightly 工具链、bpf-linker、doona 等资源，不是仅添加 feeds 就能编译。
   此处使用官方静态发行二进制，避免重复构建同一个核心。
4. **同名包覆盖风险。** 上游和本地都定义 `honk`，强制安装 feed 时可能覆盖本地包，
   连带改变 BTF 依赖、安装文件和启动逻辑。

## 此次按集成基线修复的行为

- `START/STOP/USE_PROCD` 放到 init 脚本前 11 行，让 rpcd 正确识别开机启动状态。
- 改变 UCI 的 `config_file` 后提交新命令给 procd；路径不变才发送 reload，停止中的
  服务保持停止。
- 首次在线安装时在包管理器自动 enable/start 之后再次 disable，避免默认启动。
- 已启用的服务在包升级后显式 restart，避免二进制已替换而旧进程仍在运行。
- bpffs 或 cgroup2 挂载失败时记录原因并停止启动。
- 编译后的内核检查覆盖所选 release 文档要求的 BPF、TCX、网络命名空间、NFQUEUE
  能力及 6.12 最低版本。支持作为模块的 NFQUEUE 选项允许 `=m`。

本地保留 `vmlinux-btf-local`、安装到 rootfs 的默认关闭脚本及官方二进制下载方式。
本地 init 未完整复制上游的 dae 冲突保护与旧版 UCI `enabled` 迁移；本项目不预装 dae，
也未使用过该 UCI 自启开关。如果以后引入这些使用场景，需要连同迁移逻辑一起审查。

## 更新时的判断顺序

先确认 honk 的新发布、配置语法、内核要求及资产命名，再核对 openwrt-packages 的
init、依赖与 LuCI 变动。核心故障按 honk 跟踪，OpenWrt 服务/页面问题按
openwrt-packages 跟踪。涉及默认配置或启动脚本的改动需带回本地适配；LuCI 仍按现有
策略自动跟进，并在 Release 留下实际 commit。

外置 BTF 足以支持核心数据面，但 honk 文档说明：某些可选 UDP 接收跟踪回退能力需要
内核内嵌 BTF 和 ftrace，此方案下可能不可用，不影响其余数据面启动条件。

验证覆盖离线脚本测试、真实发布资产下载校验和上游代码对照。
本次尚未重新进行完整 Linux 固件编译及 Tenda 硬件转发验证。
