# Vendored LuCI packages

`luci-app-honk/` and `luci-lib-daeuniverse/` come from
[daeuniverse/openwrt-packages](https://github.com/daeuniverse/openwrt-packages).
They are not a pinned copy that the build uses unconditionally:

- **The build takes the newest commit of upstream `main`**, the same way the
  honk binary follows the newest release (`scripts/fetch_luci.py`). Page code
  therefore does not freeze at whatever was copied here.
- **This directory is the fallback**, used when GitHub cannot be reached, rate
  limits the request, or upstream is missing one of the files the page needs
  (a rename would ship a page that cannot work). The build still succeeds and
  `honk-luci-apps.json` in the Release records `"source": "vendored"` plus the
  reason.
- Pin a revision on purpose with `LUCI_APPS_REF=<commit|tag|branch>`.
  An explicit pin fails the build if it cannot be fetched; only the default
  follows-main mode may fall back to this baseline.

The baseline below is commit
`e48b222f239e2572244c8cf495fbce79b0da7528` (main, 2026-11-03), which is also
`BASELINE_COMMIT` in `scripts/fetch_luci.py`. Keep the two in sync.

They are the LuCI entry point for the `honk` package in this repository:
`luci-app-honk` adds *Services → honk* (start/stop, Start at boot, an editor for
`/etc/honk/config.dae` and its includes, and the service log), and
`luci-lib-daeuniverse` is the shared page it is built on, including the
`/usr/libexec/daeuniverse-pkg` helper that reads package state through apk.

Why the whole feed is not added instead: buildroot keys every package by
`PKG_NAME`, which is global, and the feed also ships its own `honk`. The
installer would normally skip it (`WARNING: Not overriding core package
'honk'`), but that guard is not a guarantee: with `-f`, or a feed declared
`--force`, the feed's version is linked in and wins, and it is a different
package -- Rust sources compiled with a pinned nightly toolchain plus its own
init script, UCI defaults, `config.dae` and `vmlinux-btf*` packages. Copying
only these two packages keeps the honk binary, init script and UCI file under
our control and keeps a third-party feed out of the build.

Both packages are GPL-3.0-or-later, like the local honk package.

The local `honk/` service integration is also adapted from this upstream
baseline, while its binary comes from `daeuniverse/honk` releases and its BTF
from this build's kernel. See [the baseline decision](../docs/honk-baseline.md)
for the reasons and the reviewed local differences.

## Refreshing the fallback

The files are copied verbatim, so a diff against upstream should stay empty.
To refresh the baseline, list the files and download them at the commit you
want to record:

```sh
curl -s "https://api.github.com/repos/daeuniverse/openwrt-packages/git/trees/main?recursive=1" |
  python3 -c 'import json,sys; [print(x["path"]) for x in json.load(sys.stdin)["tree"]
              if x["type"]=="blob" and x["path"].startswith(("luci-app-honk/","luci-lib-daeuniverse/"))]'
```

Then update the commit above and `BASELINE_COMMIT` in `scripts/fetch_luci.py`.
This is optional: normal builds already follow upstream main without touching
this directory.
