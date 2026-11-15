# Development pass, 15 November 2026

The user's commit `3e3c826cec65be673ec141a1b7694988466db696` and subsequent area hardening were inspected and preserved. Police HQ belongs to Cherry Tree Hills; checks available before Police are not automatically Auburn checks.

## Progression and confirmed requirements

New seeds default to two copies of each family: Progressive Police (Police, Grapple Gun), Progressive Robber (Robber, Color Gun), Progressive Firefighter (Firefighter, Fire Axe), and Progressive Astronaut (Astronaut, Jetpack). Legacy standalone names and IDs remain readable; per-family YAML options allow legacy pools. Ordered receipts resolve a concrete stage and popup label. A previously received legacy stage is skipped.

Criminal Scan, Detective Scan, Wiretap and Surveillance remain separate items. Logic and new-seed native delivery require Police stage 1 before activating these tools. They do not grant Grapple Gun. Tool receipts arriving before their class wait for that class. Existing seeds without the new prerequisite option retain their native delivery policy.

The confirmed gas-station call-in is `objective:WI_FL_0708_VehDrop`, corroborated by native `vehicle_drop_info/vehicledrop_intro.sf`. It requires SuperBuild. The third clown requires Police and, when randomized, Detective Scan. Linear seeds safeguard early local SuperBuild and Detective Scan placement, in addition to Police and requested early Criminal Scan. This prevents these mandatory tools being placed behind their own checks; it is not a complete traversal proof.

Grace's automatic wardrobe reward is excluded as a second check for new seeds: Story Disguise COP is the single location. Its legacy ID remains available for old seeds.

## Source review

All 866 Sheet rows are imported as unverified design records; 597 match exact native keys. No Internet requirement expression becomes verified logic merely through import. Unmatched rows remain review records, not invented runtime checks. The 104 filtered reward rows have an evidence review. Grace and one proven Smallisimo activity reward are retired as duplicate detectors; seven synthetic Police HQ assignment checks are also excluded from new generation. Existing IDs are preserved.

Two stable read-only live snapshots established 20 additional exact city pickup bindings: 16 small and four large Superbricks, bringing the exact binding catalogue to 40. Evidence is in `pickup_binding_pass_2026_11_15.json`. Ambiguous bits remain excluded. Old-seed detection is enriched without changing journal identity. Source type distinguishes small Gold Plate pickups from large SuperBrick4X2 pickups.

## Area-return prototype

See `area_pass_rollback.md` and `area_pass_hardening_2026_11_15.md`. Auburn is always allowed; a local Cherry Tree Hills pass is placed on an observed Auburn opening check. Area restrictions require explicit experimental opt-in and linear mode.

Native commands capture an allowed actor/vehicle transform and invoke reviewed engine movement routines on a nearby forbidden boundary crossing. Native checks revalidate executable signatures, save binding, actor, scene, vehicle, district and a maximum 90 metre return distance. No arbitrary caller coordinates are accepted. Busy states defer; uncertain outcomes are not blindly repeated. Checkpoint identity resets even while backup readiness is pending. GUI diagnostics expose decisions.

Only synthetic foot/vehicle movement fixtures have run. No live player was teleported during this development pass. Fast travel, reloads, distant crossings, vehicle switching, aircraft/boats and real physics/collision recovery remain unproven or unsupported. This is not a general district entrance barrier. Open-world initialization and native story-ticket gates remain unavailable.

## Validation and artifacts

343 unittest executions passed, including GUI and synthetic native fixtures. 180 generated seeds across 18 profiles passed restrictive fill and reachability checks, including legacy-family toggles, starting inventory, area mode and multiworld. These checks do not prove an entire native playthrough. Logs are under `build/lego_city_undercover/next_pass`.

Use the rebuilt `build/lego_city_undercover/lego_city_undercover.apworld` with the source client and a new seed for the new pool. `docs/LCU_Chronological_Test.yaml` is the ordinary test; `docs/LCU_Area_Rollback_Test.yaml` separately opts into the boundary prototype. Install only one APWorld filename. Existing saves are not deleted or converted by this pass.

Remaining work includes complete traversal/cost logic, hundreds of unbound pickup sources, native story entrances and open-world setup, remaining reward-pair proofs, and an actual fresh-save chronological playthrough.
