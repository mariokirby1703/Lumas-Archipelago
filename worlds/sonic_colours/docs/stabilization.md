# Stabilization update: 0.5.1, schema 5

This update preserves existing immediate Red Ring, capsule, Clear/Rank,
journal/acknowledgement, save binding, progression and item delivery paths.
It does not establish a complete playable integration. Schema-5 seeds retain
their identities; do not delete journals or reuse saves with another seed.
The existing four Gecko code groups and their emitted payloads are unchanged.
Automatic installation and a workflow without manually configured codes are
deferred as requested; direct DME writes do not establish instruction-cache/JIT
coherency for executable patches.

## Production changes

White capsule ownership is configured independently and first during the normal
runtime loop, including before ReceivedItems history. A failure in progression
or gameplay-control setup no longer skips White configuration. Restart and stage
transition tests exercise the same runtime path and durable ownership receipts.
Status reports actual boost/speed hook activation separately from configuration.

Every write authorization still verifies the full PAL executable. The trusted
native snapshot avoids hashing the same executable twice in that authorization
and avoids scanning unrelated pickup models. This is not a TTL cache: an
unrelated executable modification still rejects the next write.

On Windows, more than one Dolphin process, no attributable process, or failed
process enumeration suspends the client. The backend repeats this check at the
write boundary. DME does not expose a selected PID, so the client cannot safely
choose between multiple processes. It never closes another emulator.

The APWorld includes the existing client logo and verifies its package hash.

## Extended music resource

The new resource path reads the original PAL `sound/bgm.strm.csb` and its full
87-cue catalog. It changes only existing CUE synth references; audio, cue names,
IDs, flags and synthesis/control data are retained. Seeded permutations remain
within matching synthesis/repeat/control compatibility groups. Per-world mode
also separates normal world music, bosses, Game Land, maps and menus.

67 cues participate, including compatible title/options/save/results menus,
world maps, bosses, Game Land and normal stages including both intro Acts.
20 cues remain protected: transformation music, critical jingles and synchronized
opening/ending/theme music. Credits are therefore **not randomized**. Compatibility
and exact byte readback are verified offline; timing and audible playback need
actual Dolphin testing.

From the installed Sonic client launcher, supply:

```text
--patch-all-music "ORIGINAL/sonic2010_0.cpk" "SEED_COPY/sonic2010_0.cpk" "SEED.apsonic"
```

The seed must enable music randomization. The command verifies the original PAL
CPK hash, writes a new separate CPK and adjacent JSON manifest, and refuses an
existing destination. It does not overwrite the source, edit an ISO, install
resources or change Dolphin settings. Put the output in a separate extracted
game/disc copy using your existing resource replacement workflow, then restart
emulation so title/intro resources load from that copy. Keep the vanilla copy.

Select the manifest in the connected client with:

```text
/sonicmusic "SEED_COPY/sonic2010_0.cpk.json"
```

Alternatively use `--music-resource-manifest` when launching the client. The
manifest must match the authenticated server seed and music mode. The client
reopens the actual disk resource, reconstructs and hashes the original bank,
and checks the expected seed redirects. It then uses original runtime Act cue
aliases to avoid shuffling twice. Selection is retained across reconnect in
that client process; after restarting the client, select it again. The client
cannot establish that Dolphin loaded the selected disk copy. Without a selected
resource, the existing 36-Act runtime music path remains available. An invalid
resource suspends only music projection, not location transport or item delivery.

## Validation and exact remaining blockers

The full suite passed **1,087 tests**, including the existing restrictive-fill
and seed matrices. A subsequent focused run passed **224 tests**, covering the
added GUI command with a Windows path containing spaces and package-logo checks.
Music tests cover 100 seeds in each mode, real original bank edits, a separate
original CPK copy, exact readback, protected cues, corrupted resources and foreign
seed rejection. Native tests use captured RAM and emitted PowerPC execution with
explicit native-call stubs; those stubs do not prove collision or rendering.

The reachable Dolphin instance reported `RG9P54`, not Sonic PAL `SNCP8P`.
It was correctly rejected. No guest writes or Sonic gameplay validations were
performed in this update. Earlier documented Sonic acknowledgements remain
earlier evidence, not validation of this build.

Remaining requirements have specific native gaps:

- Actual intro/stage shuffling: mission data contains position, direction,
  start-event, phantom and result metadata. A verified native transition that
  redirects both mandatory intro Acts and preserves restart/results/save-index
  attribution is missing. Post-intro Starting Act remains separate; level
  randomization is rejected rather than pretending its metadata is gameplay.
- Coloured Wisp acquisition/activation: capsule permissions are not proof of
  successful pickup or transformation. The PAL grant creates released-Wisp
  actors at `0x800FD21C`; boost-model availability at `0x801014D0` also participates
  in the held-Wisp setter at `0x801011F8`. The full released-actor delivery and
  lifecycle require native validation. This update does not change those thunks.
- Movement/story speed: Homing and Double Jump state entries are identified,
  but returning from an entry after a state transition can leave an uninitialized
  state. A safe pre-transition gate and an isolated normal-running velocity cap
  are missing. These YAML features remain unavailable.
- Egg Medal capture: the current native latch persists after host arming, but
  cannot guarantee a pickup before the first arm. A verified creation-time
  capture is missing. Per-medal route logic remains conservative until routes
  and usable Game Land abilities are verified.
- Native DeathLink/swimming: decrementing lives is not a death transition;
  writing a state pointer skips required lifecycle callbacks. A verified death
  request and reversible swim-state transition remain missing. Both stay off.
- Complete music coverage: protected synchronized music needs a timing-safe
  replacement strategy. Loading the generated copy and audible playback have
  not been verified.
- White capsules, repeated Rings/1-Ups/traps, Half Boost Refill, speed controls,
  all-eight-Wisp Terminal Velocity and final-goal transitions still need a
  complete live playthrough of this build; readback and mocked tests do not
  prove those visible effects.

For live testing use a fresh, seed-bound game: check automatic intro binding,
immediate Red Ring/capsule and both intro results acknowledgements, death and
reconnect persistence, then repeat counter rewards while alive and defer rewards
through results. Check locked/owned White and all seven coloured capsule types,
world paths, Game Land speeds and final goal. Verify title/menu/map/boss/Game Land
audio from the separate patched copy. Do not overwrite an existing unrelated save.
