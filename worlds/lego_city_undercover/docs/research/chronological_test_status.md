# Chronological restart test

The overlay now shifts 280 logical units below its original position, 40 more than
the user-confirmed previous version. All three real notification variants are
connected: indexed receipts with source slot, own receipts, and server-confirmed
ItemSend events. Preview buttons do not create real receipts or sends.

`docs/LCU_Chronological_Test.yaml` (also copied into build/lego_city_undercover)
uses linear mode and `early_criminal_scan: true`. This new optional safeguard
requests one local Ability: Scanner through the AP early-fill stage. Native Scanner
is criminal/person scan. Police remains a locked placement on an observed opening
check. The generator rejects an enabled safeguard without a Scanner in the pool,
conflicting non-local settings, or enough available early checks for both items.
The safeguard defaults off and does not alter an existing seed.

The YAML was exercised through world creation, pre-fill, restrictive fill and
reachability checks. Both early items are obtainable before the Police region gate
in the current partial model. This does not establish full story beatability in-game:
all other post-opening checks still have only the provisional Police requirement.

Detective scan now has the separate progression item `Ability: Detective Scan`
and a native AllowDetectiveMode gate; see detective_scan_lock.md. The current YAML
enables early placement for both separate scans. Its entitlement persists through
the AP receipt journal, not a fabricated 51-entry native ability flag. Old seeds
cannot contain the new item; the test UI can grant/revoke it for testing there.
The broader progressive class/ability system remains unimplemented. Do not promise
a fully randomized, softlock-free chronological run based on this template.

For the restart, keep the old slot if convenient and use an unused game slot plus
a newly generated AP seed from this YAML. Use the rebuilt APWorld for generation
and restart the native client so that it picks the newly built bridge. No old save
was deleted or edited to prepare these artifacts.

Validation: 259 tests, 258 passed and one skipped, including a complete fill of
this template and native overlay-style restoration on synthetic memory.
