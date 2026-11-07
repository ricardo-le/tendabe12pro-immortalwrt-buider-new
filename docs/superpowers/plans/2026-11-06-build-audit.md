# Firmware build audit and repair plan

Goal: preserve the Passwall and honk variants while fixing reproducible build,
runtime and release defects. Version policy remains latest published Xray
(including prereleases), latest honk, and latest LuCI with a vendored fallback.

- [x] Reproduce config derivation failures for disabled/existing symbols and
      missing honk kernel prerequisites; repair and regenerate the snapshot.
- [x] Enforce isolation for both variants and verify the installed manifest.
- [x] Reproduce honk init metadata, package-install and config reload defects
      with a shell harness; repair without requiring a router.
- [x] Reject incomplete release artifacts consistently in staging and notes;
      keep publishing a complete variant if the other fails.
- [x] Check malformed sysupgrade members and the exact kernel size boundary.
- [x] Prevent explicit LuCI pins from silently using the baseline and clear
      stale package files during fallback.
- [x] Run offline regressions, shell/JavaScript/workflow validation, inspect
      the final diff, and record the limits of local verification in README.

Validation uses Python unittest fixtures, real shell functions with procd/ubus
boundaries stubbed, and a workflow linter. Full firmware builds and actual
router startup require Linux GitHub runners and the Tenda hardware respectively.

- [x] Compare both daeuniverse repositories and document the integration/core/BTF baseline decision in docs/honk-baseline.md.

Verified: 28 offline regression tests, both config checks, actionlint, package shell syntax, LuCI JavaScript/JSON syntax, Python syntax and git diff --check. Independent read-only review found no actionable issues. Real Xray/honk release downloads and LuCI upstream staging passed; the honk host-pahole precheck was bypassed for this macOS download-only verification. Full Linux firmware build and hardware validation remain unperformed.
