# Vendored packages

`luci-app-honk/` and `luci-lib-daeuniverse/` are copied verbatim from
[daeuniverse/openwrt-packages](https://github.com/daeuniverse/openwrt-packages)
at commit `e48b222f239e2572244c8cf495fbce79b0da7528` (main, 2026-11-06).

They are the LuCI entry point for the `honk` package in this repository:
`luci-app-honk` adds *Services → honk* (start/stop, Start at boot, an editor for
`/etc/honk/config.dae` and its includes, and the service log), and
`luci-lib-daeuniverse` is the shared page it is built on, including the
`/usr/libexec/daeuniverse-pkg` helper that reads package state through apk.

Why not add the upstream feed instead: the feed also ships its own `honk`
package, and buildroot keys every package by `PKG_NAME`, which is global. What
happens then depends on the installer, not on us: `scripts/feeds` scans the
core tree first and skips a feed package whose name already exists
(`WARNING: Not overriding core package 'honk'; use -f to force`), so nothing
breaks today -- unless someone passes `-f` or the feed is declared `--force`,
in which case the feed version is linked in and wins. That version is a
different package altogether: Rust sources compiled with a pinned nightly
toolchain plus its own init script, UCI defaults, `config.dae` and the
`vmlinux-btf*` packages. Only these two LuCI packages are taken, so the honk
binary, init script and UCI file stay under our control and no third-party feed
enters the build at all.

Both packages are GPL-3.0-or-later, like the local honk package.

## Updating

```sh
# list the files the two packages consist of
curl -s "https://api.github.com/repos/daeuniverse/openwrt-packages/git/trees/main?recursive=1" |
  python3 -c 'import json,sys; [print(x["path"]) for x in json.load(sys.stdin)["tree"]
              if x["type"]=="blob" and x["path"].startswith(("luci-app-honk/","luci-lib-daeuniverse/"))]'
```

Re-download those paths into `package/`, keep `daeuniverse-pkg` executable, and
update the commit above. No local edits are made to the vendored files, so a
diff against upstream should stay empty.
