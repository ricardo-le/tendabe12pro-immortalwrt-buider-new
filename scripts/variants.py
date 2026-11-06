"""Single source of truth for the two firmware variants."""

BOARD = 'mediatek'
SUBTARGET = 'filogic'
DEVICE = 'tenda_be12-pro'
IMAGES_DIR = 'mediatek/filogic'
KERNEL_PARTITION_BYTES = 6 * 1024 * 1024  # partition@780000, size 0x600000

VARIANTS = {
    'passwall': {
        'title': 'Passwall + Xray',
        'summary': 'Passwall 全家桶 + 官方最新 Xray（含 beta/rc 预发布）',
        'config': 'tendabe12pro.config',
        'payload': 'xray',
        'release_json': 'xray-prebuilt/release.json',
        'binary': 'usr/bin/xray',
        'required': [
            'CONFIG_TARGET_mediatek_filogic_DEVICE_tenda_be12-pro=y',
            'CONFIG_PACKAGE_luci-app-passwall=y',
            'CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Xray=y',
            'CONFIG_PACKAGE_xray-core=y',
        ],
        # AdGuardHome is not preinstalled, but it is deliberately NOT forbidden:
        # it can be added back from menuconfig at any time.
        'forbidden': [],
    },
    'honk': {
        'title': 'honk（无 Passwall）',
        'summary': 'honk eBPF 透明代理 + 内嵌 doona 面板，不含 Passwall/Xray',
        'config': 'tendabe12pro-honk.config',
        'payload': 'honk',
        'release_json': 'honk-prebuilt/release.json',
        'binary': 'usr/bin/honk-core',
        'required': [
            'CONFIG_TARGET_mediatek_filogic_DEVICE_tenda_be12-pro=y',
            'CONFIG_PACKAGE_honk=y',
            'CONFIG_PACKAGE_luci-app-honk=y',
            'CONFIG_PACKAGE_luci-lib-daeuniverse=y',
            'CONFIG_PACKAGE_vmlinux-btf-local=y',
            'CONFIG_PACKAGE_kmod-veth=y',
            'CONFIG_PACKAGE_kmod-nft-queue=y',
            'CONFIG_PACKAGE_kmod-nfnetlink-queue=y',
            'CONFIG_PACKAGE_v2ray-geoip=y',
            'CONFIG_PACKAGE_v2ray-geosite=y',
            'CONFIG_KERNEL_DEBUG_INFO=y',
            '# CONFIG_KERNEL_DEBUG_INFO_REDUCED is not set',
            # Kernel/Configure/Default copies CONFIG_KERNEL_* into the kernel
            # .config (awk, stripping the KERNEL_ prefix), so this is the real
            # switch behind CONFIG_CGROUP_BPF, which honk requires.
            'CONFIG_KERNEL_CGROUP_BPF=y',
        ],
        'forbidden': [
            'CONFIG_PACKAGE_luci-app-passwall=y',
            'CONFIG_PACKAGE_luci-i18n-passwall-zh-cn=y',
            'CONFIG_PACKAGE_xray-core=y',
            'CONFIG_PACKAGE_haproxy=y',
            'CONFIG_PACKAGE_shadowsocks-rust-sslocal=y',
            'CONFIG_PACKAGE_shadowsocks-rust-ssserver=y',
            'CONFIG_PACKAGE_simple-obfs-client=y',
            'CONFIG_PACKAGE_v2ray-plugin=y',
            'CONFIG_PACKAGE_geoview=y',
            'CONFIG_PACKAGE_chinadns-ng=y',
            'CONFIG_PACKAGE_dns2socks=y',
            'CONFIG_PACKAGE_microsocks=y',
        ],
        # Options a feed adds after the base config was generated cannot be
        # disabled by editing the config, so anything under these prefixes is
        # turned off after defconfig instead.
        'forbidden_prefixes': [
            'CONFIG_PACKAGE_luci-app-passwall',
            'CONFIG_PACKAGE_luci-i18n-passwall',
        ],
    },
}

# Packages that only exist because Passwall selected them. Listing them here
# keeps the derived honk config free of the whole Passwall stack instead of
# only dropping luci-app-passwall.
PASSWALL_STACK = (
    'haproxy', 'shadowsocks-rust-sslocal', 'shadowsocks-rust-ssserver',
    'simple-obfs-client', 'v2ray-plugin', 'geoview', 'chinadns-ng',
    'dns2socks', 'microsocks', 'xray-core',
)

HONK_EXTRA_PACKAGES = (
    'honk', 'vmlinux-btf-local', 'luci-lib-daeuniverse', 'luci-app-honk',
    'kmod-veth', 'kmod-nft-queue',
    'kmod-nfnetlink-queue', 'v2ray-geoip', 'v2ray-geosite',
)
