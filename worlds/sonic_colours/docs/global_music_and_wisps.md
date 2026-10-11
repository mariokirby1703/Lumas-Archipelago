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

Music On uses one eligible pool for Acts, world maps, Game Land, bosses and
menus. Compatibility no longer splits that pool. The destination keeps its
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
eligible donor. Mixed stems from unrelated donors, protected edits, unknown
references, graph damage and combined legacy/current layouts are rejected.
Exact previous compatible-CUE layouts can migrate. Music Off restores the
complete byte-for-byte vanilla bank. Native mission aliases stay vanilla so
the old Act-only permutation cannot compose with this bank shuffle.

Excluded source and destination cues: `bgm_jingle_*`, `bgm_pha_*`,
`bgm_sys_theme`, `bgm_sys_op`, `bgm_sys_end`. These retain synchronized
opening/ending, transformation and critical jingle behavior.

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
