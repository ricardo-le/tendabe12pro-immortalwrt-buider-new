# SPDX-License-Identifier: GPL-3.0-or-later
#
# Ships the kernel BTF of *this* build as /usr/lib/debug/boot/vmlinux, the
# second path honk (and libbpf) look at when /sys/kernel/btf/vmlinux is absent.
#
# Why not just enable CONFIG_KERNEL_DEBUG_INFO_BTF? Because the Tenda BE12 Pro
# has a 6 MB kernel partition and the current kernel already uses ~4.6 MB of
# it; an in-kernel .BTF section can overflow it. The BTF blob is ~5 MB
# uncompressed and lands in the 90 MB rootfs instead, where xz compresses it.
#
# pahole comes from the host (apt install dwarves), because OpenWrt only builds
# its own copy when CONFIG_KERNEL_DEBUG_INFO_BTF is selected. The kernel must
# be built with full DWARF, i.e. KERNEL_DEBUG_INFO=y and
# KERNEL_DEBUG_INFO_REDUCED unset -- which the honk variant config does.
#
# The package is built after target/compile in `make world`, so
# $(LINUX_DIR)/vmlinux exists by then.

include $(TOPDIR)/rules.mk

include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=vmlinux-btf-local
PKG_VERSION:=$(if $(LINUX_VERSION),$(LINUX_VERSION),$(if $(KERNEL_PATCHVER),$(KERNEL_PATCHVER),1))
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/vmlinux-btf-local
  SECTION:=kernel
  CATEGORY:=Kernel
  PKGARCH:=all
  TITLE:=Detached kernel BTF generated from this build
  URL:=https://github.com/daeuniverse/honk
endef

define Package/vmlinux-btf-local/description
 Detached BTF blob produced from the vmlinux of this build and installed where
 libbpf looks for it. Required by honk for its CO-RE relocations on kernels
 that do not carry their own BTF.
endef

define Build/Compile
	mkdir -p $(PKG_BUILD_DIR)
	@command -v pahole >/dev/null 2>&1 || { \
		echo "vmlinux-btf-local: pahole not found on the build host"; \
		echo "vmlinux-btf-local: needs >= 1.24 for kernel 6.18 DWARF (DW_TAG_unspecified_type)"; \
		exit 1; }
	@test -s $(LINUX_DIR)/vmlinux || { \
		echo "vmlinux-btf-local: $(LINUX_DIR)/vmlinux is missing; build the kernel first"; \
		exit 1; }
	pahole --btf_encode_detached=$(PKG_BUILD_DIR)/vmlinux.btf $(LINUX_DIR)/vmlinux
	@test -s $(PKG_BUILD_DIR)/vmlinux.btf || { \
		echo "vmlinux-btf-local: pahole produced no BTF blob"; \
		exit 1; }
	@ls -l $(PKG_BUILD_DIR)/vmlinux.btf
endef

define Package/vmlinux-btf-local/install
	$(INSTALL_DIR) $(1)/usr/lib/debug/boot
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/vmlinux.btf $(1)/usr/lib/debug/boot/vmlinux
endef

$(eval $(call BuildPackage,vmlinux-btf-local))
