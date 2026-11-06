# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenWrt package for honk-core, the eBPF transparent proxy engine of
# daeuniverse/honk.
#
# The binary is the official static musl aarch64 release of the "full" variant
# (Clash API + native API + embedded doona dashboard, eBPF object embedded).
# scripts/prepare_honk.py downloads it, verifies its SHA-256 against the
# release's SHA256SUMS, and writes version.mk next to this file.
#
# The package is modelled on honk/files of daeuniverse/openwrt-packages
# (GPL-3.0-or-later) so that the init script, the UCI file and the runtime
# paths match what that feed installs.

# $(CURDIR) is the buildroot top directory and $(MAKEFILE_LIST) grows with
# every include, so resolve this directory before the first include.
PKG_DIR:=$(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

include $(TOPDIR)/rules.mk

-include $(PKG_DIR)/version.mk

PKG_NAME:=honk
PKG_VERSION:=$(if $(HONK_VERSION),$(HONK_VERSION),0.1.0_beta5)
PKG_RELEASE:=1
PKG_LICENSE:=GPL-3.0-only
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

HONK_BIN:=$(TOPDIR)/honk-prebuilt/honk-core

define Package/honk
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=Web Servers/Proxies
  TITLE:=eBPF transparent proxy engine (honk-core)
  URL:=https://github.com/daeuniverse/honk
  LICENSE:=GPL-3.0-only
  # The eBPF datapath needs TC-bpf plus a veth pair and the daens namespace,
  # its first-packet staging needs the nftables queue expressions over
  # nfnetlink_queue, and its CO-RE relocations need kernel BTF, which the
  # vmlinux-btf-local package ships as /usr/lib/debug/boot/vmlinux.
  DEPENDS:=+ca-bundle +kmod-veth +kmod-sched-core +kmod-sched-bpf \
           +kmod-nft-core +kmod-nft-queue +kmod-nfnetlink-queue \
           +kmod-nf-conntrack +vmlinux-btf-local +v2ray-geoip +v2ray-geosite
endef

define Package/honk/description
 honk is an experimental eBPF transparent proxy engine written in Rust.
 This package installs the official static musl aarch64 build of honk-core
 with the Clash API, the native API and the embedded doona dashboard, a procd
 init script and a minimal /etc/honk/config.dae. The service is disabled by
 default: add nodes and routing rules first, then enable it.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	@test -x $(HONK_BIN) || { \
		echo "honk: $(HONK_BIN) is missing; run scripts/prepare_honk.py first"; \
		exit 1; }
endef

define Build/Compile
endef

define Package/honk/conffiles
/etc/config/honk
/etc/honk/config.dae
endef

define Package/honk/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(HONK_BIN) $(1)/usr/bin/honk-core
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_DIR)/files/honk.init $(1)/etc/init.d/honk
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) $(PKG_DIR)/files/honk.config $(1)/etc/config/honk
	$(INSTALL_DIR) $(1)/etc/honk
	$(INSTALL_CONF) $(PKG_DIR)/files/config.dae $(1)/etc/honk/config.dae
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) $(PKG_DIR)/files/90-honk-disable $(1)/etc/uci-defaults/90-honk-disable
	$(INSTALL_DIR) $(1)/lib/upgrade/keep.d
	printf '%s\n' '/etc/honk/data/' > $(1)/lib/upgrade/keep.d/honk
	# v2ray-geoip/geosite install the data files under /usr/share/v2ray;
	# honk looks in /usr/share/honk before /usr/share/dae.
	$(INSTALL_DIR) $(1)/usr/share/honk
	$(LN) ../v2ray/geoip.dat $(1)/usr/share/honk/geoip.dat
	$(LN) ../v2ray/geosite.dat $(1)/usr/share/honk/geosite.dat
endef

$(eval $(call BuildPackage,honk))
