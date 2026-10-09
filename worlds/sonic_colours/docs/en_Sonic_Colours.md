For the current client and an in-game test YAML, see
[Immediate checks and native gameplay testing](immediate_checks.md).
This integration is incomplete; the historical details below do not describe the new pickup policy.

# Sonic Colours (Wii)

`ap-status=Custom` ? PAL `SNCP8P`, revision 0. Development version 0.2.0.

Eight Wisp unlocks are real shuffled progression items. Default generation does
not precollect them. Unknown clear routes are explicitly provisional until the
user supplies exact logic; optional Red Ring routes conservatively require all
Wisps. No complete native multiworld has been verified yet.

Checks: 45 story clears; optional 21 Game Land clears and seven Emerald rewards;
180 individual Red Rings or 36 all-five checks. S/A/B/C rank IDs reserve four
thresholds for each of 44 candidates; rank availability is not yet live-proven.
No D check exists. Emerald rewards require all three stages of their Game Land,
even when clear locations are off. Actual client goals require native completion.

AP Red Ring bundles contain 1, 5 or 10 units independently of physical pickups.
At reduction 40, Game Land Act 2 gates are 10..70 and Act 3 gates 80..140; first
acts are free. All 14 non-free gates remain unique and positive at extreme settings.
Seven AP Emerald items express Super Sonic permission; there is no extra item.

Capsule sanity reserves distinct mission/file/layer/object/instance identities:
456 story candidates, 232 mapped Game Land candidates, 18 unmatched excluded.
Native opening, subtype and accessibility proof are required per instance before
activation. Non-off capsule modes reject while no validated subset exists.

Rings/1-Up filler and Ring Loss Trap use a durable guarded scheduler. Trap share
is computed only from filler after progression, rounded half up; weights are
0/1/3/6. Native effects and randomizers still have individual proof gaps listed
in [development](development.md). See [setup](setup_en.md) for New Game, forced
intro, any-slot binding, resume and schema migration.
