# Sonic Colours Wii PAL v0.6.0: live experiments

Current global music implementation and validation limits are described in
[global_music_and_wisps.md](global_music_and_wisps.md). The notes below retain
the original experiment context; direct injection remains experimental.

This is an intentionally experimental build for PAL `SNCP8P` revision 0 only.
**Do not test on your only save. Back up Dolphin data and use a disposable seed.**
The package contains no game binaries or patched game files.

## What is implemented and what is not verified

1. A fixed Tropical Resort introduction, two World Progression policies and
   stable Eggman Heart names/IDs are implemented at the Python logic/native
   permission layer. Both modes still require gameplay and generation testing.
2. Music On (default) finds the original 87-cue CSB at the captured address
   `0x9017E8A0` (or a candidate pointer), but **only after hashing and fully
   validating the bank**. It now replaces terminal audio references across
   one global pool while retaining destination control graphs;
   music Off reverts them to original. It does not overwrite an ISO/CPK, or
   write any game code. The existing playing track may be cached; play into a
   world map, Game Land, or reload a scene to listen for new music. The default
   seed mapping is deterministic across eligible music categories. Actual
   playback in Dolphin remains unverified.
3. The direct PPC injector is **opt-in only**. It writes 10 unmodified Gecko
   payloads into `0x80001800..0x80003000`, a former codehandler area that was
   all zero in specific captures with Gecko disabled. The complete current Gecko
   export occupies 3248 bytes of its table budget. Original DOL text starts `0x80004000`.
   But ZERO in captured memory DOES NOT prove this scratch region is permanently
   reserved or executable. Dolphin may overwrite it, and DME does not provide
   JIT/ICache invalidation. A successful readback does NOT prove execution.

## Quick, controlled A/B test

**Recommended first:** Leave `--experimental-direct-hooks` OFF and keep your
current four Gecko codes enabled, so you can test World Progression and the
new in-memory music bank with the stable native hook delivery path.

**Dangerous second test:** Close Dolphin; disable all four Gecko code groups;
start Dolphin normally and then start the AP client with:

```text
--experimental-direct-hooks "YOUR-SEED.apsonic"
```

You can pass the flag in the Sonic Client's launcher arguments. Only test with
exactly one Dolphin process. Watch `/sonicstatus` and `/sonicdebug` for
`experimental_direct_hooks`. The status `installed_in_guest_ram: true` means
**only that guest RAM was written**, NOT that Dolphin's JIT has executed it.
Try a Wisp/Boost pickup, a Red Ring, Game Land Eggman Heart and a World Unlock.
If Dolphin crashes, restart the emulator and client and resume from a disposable
save. Do NOT try to hot-uninstall code while emulation is running.

The installer refuses unexpected PAL executable hashes, nonzero scratch RAM,
unexpected original hook words and previously installed Gecko hooks. Failure
or partial installation requires a complete emulator/client restart.

## What to send back

- The client status/debug JSON, including `music_randomization`,
  `experimental_direct_hooks`, native hook statuses and current scene.
- Before/after screenshots of a World Unlock in each `world_progression` mode.
- For music: what song was audible on the Grand World Map and Game Land, plus
  whether restarting the music by changing screens made a difference.
- For the dangerous injector: whether any changed native behavior actually
  occurred and whether the guest restarted/crashed. DO NOT interpret readback
  alone as success.

## If the direct installer fails

There is not currently an exposed DME API to force Dolphin JIT cache
invalidation. The long-term correct solution would be a documented Dolphin
IPC/debugger/patch API or a verified guest-side native install and cache flush
strategy. No guaranteed Gecko-free full integration is claimed here.

## Random Capsules item

New seeds include the progression item `Random Capsules` (stable item offset 35).
It independently gates question-mark ReleaseBoxSmall capsules with native
colour -1 and either native special marker +148 or +14A. White Boost ownership does not unlock them.
The native alternate-content marker is preserved during ghost/content model
replacement and collision re-registration. The native question-mark multi-Wisp
variant uses its original reward path. Fixed White capsules retain their separate
White permission. Update the APWorld and Gecko codes, restart both programs, and
regenerate the seed to include the new item in the pool. Old seeds have no
Random Capsules item unless explicitly granted by the server.

Live evidence identifies the special capsule before collection; after pickup
its actor was removed. The Eggman outcome was reported by the player, not
independently captured. The new lock/unlock and preserved random pickup
behavior still require live Dolphin validation.
