# Sonic Colours (Wii) setup ? development version 0.2.0

`ap-status=Custom`. Wii PAL `SNCP8P`, revision 0 only. This is an unfinished
integration: generation and the client infrastructure work offline; a complete
native playthrough has not been verified. Do not use this build for a live race.

## Migration

The public game key is now **Sonic Colours (Wii)** and slot schema is 2. Regenerate
old YAML/server seeds and `.apsonic` files; version-1 files are rejected with a
migration message. Existing stable item/location IDs are retained: the removed
extra Super Sonic item and D-rank IDs are gaps, never reassigned. The game change
requires a new server room; do not attach a v2 client to an old room.

Use [SonicColours.yaml](../examples/SonicColours.yaml). Eight Wisp items are
shuffled normally when `wisp_unlocks: archipelago`, with zero automatic starting
Wisps. Standard AP start inventory remains available. Unknown clear routes use an
explicit provisional accessibility policy; unknown Red Ring routes require all
Wisps conservatively. The user will supply exact requirements later. Provisional
clear accessibility is not a proof that every native route is beatable.

## New Game and resume

Back up your Wii save using Dolphin's save export workflow first. For a new seed,
choose **New Game**. The game forces Tropical Resort Acts 1 and 2 before its save
selection. Choose any available save slot through the normal game menu; no Slot-1
rule applies. The client never erases or overwrites a save automatically.

Connect to the intended seed before the intro and use `/sonicnewgame` to confirm
intent. This command does not bypass native verification. The client must also
corroborate the New Game transition and independent fresh-state fields. Those
native fields are still unresolved in this build, so confirmed intro attribution
is not yet operational against the real game.

The implemented flow is UNBOUND_BOOTSTRAP ? MANDATORY_PROLOGUE ?
VANILLA_SAVE_SELECTION ? BOUND_PLAYTHROUGH, with same-seed RESUME. Proven prologue
checks are journaled locally with an epoch, then reconciled against the selected
save before sending. A verified stable save identity is required; an internal
slot index or heap pointer alone is insufficient. Existing unrelated saves,
switching identities and progress rollback stop attribution and writes.

Selecting `starting_act` is currently an AP research-model setting. Native startup
still forces the two intro acts; alternative post-intro entry needs a verified map
access hook. No native starting-act redirect is claimed.

## Installation and launch

Archipelago 0.6.7+, 64-bit Dolphin and the Python
[dolphin-memory-engine library](https://github.com/randovania/py-dolphin-memory-engine)
are required. Only one Dolphin instance should be open. It must actually be
emulating the game; an empty Dolphin window returns `noEmu`.

```powershell
.venv/Scripts/python.exe -m pip install -r worlds/sonic_colours/requirements.txt
.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch --nogui --connect localhost:38281 --name SonicPlayer
```

For a packaged AP installation, place `build/apworlds/sonic_colours.apworld` in
`custom_worlds` and restart Archipelago. A source checkout already loads it from
`worlds`; avoid duplicate installations. Launcher registers Sonic Colours (Wii)
Client and `.apsonic` files. AP URI, password, name and nogui arguments are supported.

The exact executable's whole-DOL provenance hash is
`92aefe33b577493b492f8433ca68b90d25d29d2f6d9c85310a6829481281f8a9`.
Both mapped text sections, disc ID and revision are verified before native reads.
Other regions, revisions or patched code fail closed.

Commands: `/sonic`, `/sonicstatus`, `/sonicdebug`, `/sonicnewgame`, and
`/sonicrecover skip INDEX` for an interrupted uncertain effect only. Journals in
Archipelago's `sonic_colours_journals` directory retain receipts, bootstrap evidence
and checks. Confirmed effects are never replayed after a crash or reconnect.

## Feature restrictions

Default generation has 253 checks. AP Red Ring bundles and physical Red Rings are
independent. Seven AP Emerald items express Super Sonic permission automatically;
with Emerald items off, native acquisition remains the intended authority. There
is no separate Super Sonic item, option or goal.

Rank checks offer S/A/B/C/All (four thresholds); D gives no check. Native rank
eligibility and saved best-rank readers remain unverified, so non-off modes still
reject generation. Level/music shuffle, swimming, DeathLink and Wisp discoveries
also retain precise per-feature refusals until their native mechanisms are proven.
DeathLink network handling is connected in code; native kill is unresolved.

`wisp_capsule_sanity: off/story/all` is implemented with an instance validation
overlay. The catalog has 456 story, 232 mapped Game Land and 18 unmatched
candidates. No instance has native identity/accessibility validation yet; story/all
therefore reject rather than silently creating unreachable or fake checks.

Ordinary Rings, 1-Ups and Ring Loss Trap remain queued until a verified stats
pointer and safe write context exist. Candidate progress reads are diagnostic,
not automatically sent as checks from an unidentified save. No code patch or CPK
edit is installed in this build, so there is no injected trap to revert.
