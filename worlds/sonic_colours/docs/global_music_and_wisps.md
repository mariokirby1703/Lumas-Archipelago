# Global BGM and native Wisp correction

## Native Wisp enum

AP item IDs and names are unchanged. PAL colour/permission indices are:

| Index | AP item |
|---|---|
| 0 | Yellow Drill Wisp |
| 1 | Cyan Laser Wisp |
| 2 | Pink Spikes Wisp |
| 3 | Orange Rocket Wisp |
| 4 | Purple Frenzy Wisp |
| 5 | Blue Cube Wisp |
| 6 | Green Hover Wisp |

The original executable's indexed sound table at `0x80765390` identifies
Laser, Spike, Rocket, Rodeo, Puzzle and Astronautes at indices 1..6.
The native permission query at `0x8003BAAC` directly tests `1 << colour`.
The previous host order incorrectly granted Cube for Rocket and projected
Hover to index 3. Live inspection found a Green capsule at native colour 6
with only permission 0x20 enabled. Save/live projection, interception,
discovery decoding and capsule accessibility metadata now use one native enum.
Location and item IDs do not move. Regenerate future seeds for corrected
capsule accessibility rules; a generated old seed's server logic stays fixed.

The user confirmed Hover capsules activated after updating the client.
Subsequent native readback found real content models, initialized collision
objects and the Hover permission enabled. Cube permission was also enabled
because the authenticated server history now contains Blue Cube Wisp. An
unowned-Cube lock therefore still needs a suitable seed for its own live test.

Singleton permanent grants from authenticated ReceivedItems packets have their
own durable journal set. This lets newly received Wisps unlock while an older
ordered consumable ledger is desynchronized. Team/slot/seed authentication and
native save attribution still apply. Filler, traps, progressive speed and Red
Ring counters cannot enter this grant set or be replayed through it.
`/sonicsync` requests the complete server history without discarding receipts.

## One global music pool

Music On uses one global pool of the 78 looping cues, across Acts, maps,
Game Land, bosses, menus and Wisp transformations. Nine finite cues stay vanilla
as both sources and destinations, following the user's revised requirement.
There are no category or compatibility subpools. The destination keeps its
original CUE, SYNTH graph, ISAAC controls, filters, gain/envelopes and routing.
Only terminal SYNTH `lnkname` references change to existing donor AAX audio.
No modified ISO, external music/CPK, new allocation or code hook is required.

The original bank has 87 cues and 137 terminal leaves, with one- or two-leaf
graphs. A destination with one leaf plays the donor's normal stem. A two-leaf
destination uses the donor's normal/fx stems, or its single stem for both
native-controlled branches. This keeps destination Boost/Sleep/underwater
controls even when the donor is a world-map or menu track. SOUND_ELEMENT
descriptors and source AAX loop data remain original; their actual playback,
gain and transitions still require listening in Dolphin.

`bgm_graphs.json` records exact original field locations and reference values.
Validation reconstructs every permitted field and hashes the entire original
bank, then verifies that each destination's audio vector comes from one
catalog donor. Mixed stems from unrelated donors, unauthorized field edits, unknown
references, graph damage and combined legacy/current layouts are rejected.
Exact previous compatible-CUE layouts can migrate. Music Off restores the
complete byte-for-byte vanilla bank. Native mission aliases stay vanilla so
the old Act-only permutation cannot compose with this bank shuffle.

Finite exclusions, derived from the original AAX loop-segment flags:
`bgm_sys_theme`, `bgm_sys_op`, `bgm_sys_end`, `bgm_stg720_elv`,
`bgm_jingle_mlt_clear`, `bgm_jingle_stg_clear`, `bgm_jingle_boss_clear`,
`bgm_jingle_drown`, `bgm_pha_rkt`. Their own audio references remain original;
they can never be assigned to another destination, including forced music tests.
Looping jingles such as Super Sonic remain in the global pool.

Recovery still accepts the previously shipped all-87 audio-leaf layout, so a
client update safely replaces an already loaded finite donor and restores the
excluded slots. Every new mapping must be a full 87-cue bijection with these
nine fixed points. The old protected/compatible CUE-root whitelist applies only
to historical patch recovery. The optional exporter uses this same planner.

The seed mapping is deterministic and avoids self/identical-audio mappings
where possible. `/sonicmusictest DESTINATION_CUE DONOR_CUE` provides a clearly
reported temporary reciprocal swap for audible validation; it does not alter
the seed or bypass validation. `/sonicmusictest off` restores the seed mapping.

Critical listening test:

```text
/sonicmusictest bgm_stg530_qua bgm_zmap_rso
```

Wait for the bank update, then re-enter Aquarium Park Act 3. Listen for
Tropical Resort world-map music, then check Boost and underwater effects.
Also test an Act donor on a world map, Game Land/boss/menu playback, looping,
the ordinary seed mapping, and Music Off. Until those are heard, table/readback
and offline tests alone are not a completed global-playback validation.

## Wisp music in the same global pool

Nine looping PAL `bgm_pha_*` cues are eligible sources and destinations;
finite Orange Rocket (`bgm_pha_rkt`) remains vanilla,
with no new YAML option. `music_randomization: true` shuffles them with Acts,
maps, Game Land, bosses and menus. The original native selector `801F8DB0`
indexes the table at `80771970` by the same native colour enum used for Wisp
permissions. These are verified associations, not abbreviation guesses:

| Cue | Native transformation / selector |
| --- | --- |
| `bgm_pha_spn` | Yellow Drill, colour 0 |
| `bgm_pha_lsr` | Cyan Laser, colour 1 |
| `bgm_pha_spk` | Pink Spikes, colour 2 |
| `bgm_pha_rkt` | Orange Rocket, colour 3 |
| `bgm_pha_rod` | Purple Frenzy, colour 4 |
| `bgm_pha_pzl` | Blue Cube, colour 5 |
| `bgm_pha_ast` | Green Hover, colour 6 |
| `bgm_pha_spn_wtr` | Drill colour 0 with actor+DD underwater flag |
| `bgm_pha_multi_common` | Native multi-Wisp mode 2, variant 0 |
| `bgm_pha_multi_united` | Native multi-Wisp mode 2, variant 1 |

The multi-Wisp selector remains mode/variant based; it is not reassigned to a
single colour. Actor+104's Super Sonic override still requests
`bgm_jingle_super_sonic`, whose audio now participates in the global shuffle.
Wisp-start requests go through `80126554`; Wisp-end
events retain native `80123730` handle release/fade. No player timer, stage cue
identity, playback handle, activation callback or executable is patched by
music randomization.

Original Wisp synths are single-leaf stereo streams, format 0 at 48 kHz, each
with a 304-byte ISAAC filter graph. Their destination cue flags, filter graph,
gain (including Laser 1399, Drill underwater 1100 and Cube p3d gain 800), routing
and envelopes remain byte-identical. An Act receiving a Wisp donor retains its
normal/FX graph; a Wisp receiving an Act donor uses the donor's normal audio
through the Wisp's own filter. The native underwater/multi selectors still
request their original distinct cues, now containing the globally assigned
audio. Donor SOUND_ELEMENT metadata and AAX data remain original and do not
need new assets, CPK patches or music-specific Gecko codes.

`tools/analyze_wisp_music.py` reproduces `data/bgm_transformations.json` from
the original ELF/CPK, including cue table entries, gains, formats and AAX loop
segments. Recovery retains the exact prior legacy CUE whitelist and validates
the expanded current audio-leaf donor set against the canonical bank hash.
Earlier resident global banks can migrate; Off restores the entire original.

**Live finite-track failure and revised policy:** On 2026-10-11 the user heard
`bgm_jingle_boss_clear` stop after about five seconds in Tropical Resort Act 1.
Read-only Dolphin inspection confirmed this donor and the original Act root's
`repeat=1`; that field does not provide the missing waveform loop. No unsupported
repeat value, AAX metadata or audio code was modified. The user then requested
excluding all finite music instead of introducing a native loop adaptation.
`tools/analyze_music_playback.py` reproduces `data/bgm_playback.json` from the
original CPK. The planner, writer, test command and diagnostics now enforce and
report the same nine exclusions. The revised exclusion is tested offline;
audible post-update playback and looping remain to be checked in Dolphin.

Audible tests, after the map-crash verification:

```text
/sonicmusictest bgm_stg120_rso bgm_pha_pzl
/sonicmusictest bgm_pha_ast bgm_zmap_rso
```

The first plays Cube music in Tropical Resort Act 2 after re-entry. The second
targets the actual Green Hover transformation with Tropical Resort map music;
activate and end Hover and verify stage-music restoration. Also test Drill
underwater, both multi-Wisp variants, loop duration, vanilla Rocket playback and
Off. Re-enter/retrigger a cue after updating the bank because active CRI voices
may retain cached audio. `/sonicmusictest off` clears the temporary test pair.
All these audible/native timing checks are pending, explicitly deferred by the
user until the next live session. Offline coverage includes all 54 reciprocal
Wisp/category combinations, canonical recovery, destination-control identity,
the resident write transaction and vanilla restore. Additional coverage checks
all 6,084 looping source/destination combinations against the original bank,
finite-track exclusion, migration from all-87 banks and byte-exact vanilla restore.
These are offline resource tests.

## Act 6 return with a locked successor

On 2026-10-11, Aquarium Park Act 6 was completed as the third completed Act
in that world. The return to the world map failed at PC `8026C93C`, reading
`00000008`. The live Aquarium map actor had transition phase 2 and null
`+7EC`; the boss node remained locked. Original PAL `802693AC` creates this
optional outgoing-path pointer only for an eligible connection, while the
`-3` animation cleanup in `8026C904` assumes it exists.

The new C2 at `8026C938` retains ordinary nonnull-path behavior and redirects
only null-path cleanup to native `8026C984`, which ends the animation.
It does not grant Acts, clear flags or boss access. The combined four-group
export now shares one disc guard/conditional scope, retaining every original
instruction guard and the standard Dolphin code-list size limit. Enable all
four groups together and restart emulation when installing the new export.

The null/non-null instruction paths and original executable signatures are
tested offline. A repeat Act-6 completion in Dolphin remains required; the
reported crash itself is live-confirmed, the repair is not yet live-verified.

On 2026-10-11 the user-installed export exposed a verifier regression: the
`8026C938` C2 was missing from executable hash normalization. Exact payload,
header length and return-branch verification now precede normalization of
that single displaced instruction. A read-only check against running Dolphin
then recovered the complete original PAL executable hash successfully.
Corrupted payloads, wrong returns and unrelated executable changes remain
rejected. This verifies installed-code recognition, not the Act-6 crash repair.
