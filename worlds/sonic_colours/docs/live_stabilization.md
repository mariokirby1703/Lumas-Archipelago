# PAL stabilization, 2026-10-11

This change preserves schema 6, the fixed introduction, existing IDs, immediate
pickups, server acknowledgements, and the default Gecko installation path.

## Implemented

- Eggman Hearts: native pickup at `0x802F27C4` authenticates the current stage,
  mission, profile, manager, actor, ORC record, instance and exact placement.
  Arming no longer depends on finding the streamed actor in a polling snapshot.
  A seed-owned 21-bit latch survives scene exits and is journaled before rearming.
  Disappearance, score and completion do not award a Heart.
- Random Capsules: both special markers `+0x148` (question-mark multi-Wisp)
  and `+0x14A` (EggMask random rewards) use the independent Random Capsules item.
  Native reward paths and collision/model registration remain intact. Fixed
  White capsules retain their own permission. The original CPK audit is in
  `random_capsule_orc_audit.json`; every original Game Land layer was scanned.
- Full Boost Refill, ID `847000036`, sets the verified native maximum. Half
  Boost Refill adds half the maximum, capped at maximum. Successful refills
  before White ownership permit temporary use of that gauge, without allowing
  vanilla grants or opening White capsules. Depletion or context change consumes
  the durable grant; reconnect cannot replay the receipt.
- Filler weights: Rings 40%, 1-Up 30%, Half Boost Refill 20%, Full Boost Refill 10%.
- Music uses original AAX identities when choosing compatible cues. Aquarium
  Acts 1/4, 2/5 and 3/6 share audio despite different cue names; mappings now avoid
  those aliases where a complete compatible matching exists. A map self-mapping
  in the reported seed is also eliminated. Native filter compatibility and
  immutable-original restoration remain enforced.
- Open Acts: the native availability setter now gates story bank-A bits before
  map events. Boss availability uses six genuine clears in that world. Host code
  no longer relocks entered/cleared map nodes after native navigation begins.
  Genuine completion bank-C bits are not fabricated.
- Write guards reuse the freshly verified scene/profile snapshot rather than
  hashing twice and rescanning every pickup for each field write.

## Evidence and limits

The original PAL executable, CPK and supplied captures support the addresses,
ORC placement and audio identity analysis. Automated tests execute emitted PPC
through an instruction adapter and exercise durable journals and the real
CommonClient protocol against a local WebSocket server. These are offline tests,
not proof of Dolphin JIT execution or public-server gameplay.

Read-only live Dolphin validation after the user's code update verified the
full PAL executable and all ten required hook bodies, mutable data ranges and
return branches. See `stabilization_live_hooks.json`. The complete export is
3256 bytes, within the native Gecko table budget. Legacy payloads are recognized
exactly but cannot silently arm the new operations.

At the subsequent Game Land 2-1 observation the Heart hook's 14 data words were
all zero. Installation is therefore verified, but live arming and pickup delivery
are not yet established for this build. Client status is needed before collecting.
Do not treat installation readback as a working live Heart check.

Still requiring controlled gameplay validation: all Heart pickups (particularly
2-1 and 4-1), both Random Capsule variants and their original rewards, temporary
refill use/depletion before White ownership, audible Aquarium music after scene
reload, and Act 6 first in Open Acts followed by all six genuine clears. The
reported camera failure cannot be declared resolved solely from offline tests.
No guaranteed Gecko-free installation is claimed.

## Rebuild

From the repository root:

```powershell
.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py
```

Output: `build/apworlds/sonic_colours.apworld`. Install it together with the full
current `data/SNCP8P_capsule_refresh.ini`, then restart client and emulation.
Generate a new seed for the new Full Boost Refill item and filler distribution.
The manifest records the exact commit, dirty state and content build ID.
