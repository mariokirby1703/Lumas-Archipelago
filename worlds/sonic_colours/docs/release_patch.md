# Release patch build

Run python worlds/sonic_colours/build_apworld.py. The output is
build/apworlds/sonic_colours.apworld. Deterministic ZIP metadata records the
commit, dirty state and SHA256 of shipped implementation files.

The tools allowlist is __init__.py, build_hud_overlay.py, hud_cpk.py,
hud_gncp.py, hud_original_assets.py, hud_preflight.py and hud_tpl.py.
Package-relative imports work from the ZIP without a checkout. Research
and diagnostic tools remain excluded.

Do not package notes, original resources, ISO/CPK/DOL files, RAM dumps,
generated GNCP/TLS files, build outputs or dependency archives. WIT and its
libraries are downloaded locally from the hash-pinned official GPL bundle.

Native payloads are rebuilt from the existing Python PPC builders. Player
containers reference native and resource-transformation fingerprints. No
complete original executable/resource file is used as a distributed delta.
Original-byte predicates are minimal signatures, not full source resources.

Run the container, ZIP import, native DOL and existing Sonic regression
suite before release. Compare failures with the unchanged baseline rather
than weakening tests. Complete the live matrix in native_patch_migration.md;
WIT VERIFY alone does not prove gameplay correctness.
