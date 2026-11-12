# Active character, attached objects and Job values

All RVAs apply only to the exact executable hash documented in inventory_layout.md.
No engine function was invoked and no game memory was written.

## Active character

Native helpers 0x7e43c0 and 0x7e43d0 read player pointers at RVAs 0x1c7d3e0 and 0x1c7d3f8.
Script-global setup names cPlayer1/cPlayer2; 0x4be20 resolves these players using an embedded interface
at actor+0x10 and virtual slot +0x1e0. In the live process that accessor was 0x6697d0 and returned the interface.
Typed script methods check bit 0x1000 at interface+0xc4 and subtract 0x10 to get the actor.
The reader therefore checks actor+0xd4. A generic entity-reference lookup instead resolved an associated
LegoCityLevelContainer during investigation and must not be confused with the actor itself.

Model metadata is at actor+0x650. Its signed short model id at +8 and internal name pointer at +0x30
are cross-checked against the model-manager table. The paused live test read model 227, COP,
matching the equipped Police character. A live outfit-change transition with this new field is still untested.

## Attached objects

Character_GetItemOut is a command, not a held-item getter. Generic wrapper 0x4a1e80 dispatches through
vtable+0x28 to typed method 0x112ab0. It uses the item controller returned by 0x66a420 (actor+0x8a0).
Our code only reads the pointer and never invokes the command.
The item-name lookup at 0x7c5100 traverses controller+0x90, with next-node at +8, definition pointer at +0x10,
and an inline name at definition+0x58. The reader bounds traversal, rejects cycles and rechecks the links.

With the user paused holding the office key, the list contained four PDA tools and M02_Dspot_key_item.
This confirms key presence in the actor's object list. It does not establish a generic hand-held-item flag,
permanent key ownership or consumption/reload behavior. The output is deliberately chief_office_key_present.

## Context

The InContext name getter 0x760a10 leads through generic dispatcher 0x4a1e80 to typed method 0x7612c0.
It compares the requested name against 0x66a080's result. That helper reads actor+0x6b0/+0x6b8 and action
pointer +0x6c0. If the two integers are equal, it takes a signed short from action+0x68+0xb6 instead.
The context manager is referenced at RVA 0x17ec090; count is +0x8f0, inline pointer array +0xf0,
and the selected definition's +8 pointer supplies the context name.

Live paused-key state: index 46, Default. This does not establish a carrying or detective context.
Older scan snapshots lack this new field: DetectiveMove detection needs a future real scan transition.
No context lock has been implemented or tested.

## Story values

Job_GetValue resolves the manager at RVA 0x17eca08. Helper 0xddbf0 returns manager+0xe0,
whose registry pointer is +0 and 32-bit count +8. Each 24-byte record contains job hash +0,
field-pointer-array +8 and unsigned 16-bit field count +0x10.
Helper 0xd9650 matches field hashes at value-object+0xc. The live registry contained all 662 expected jobs.

JobValue_Int vtable RVA 0xc46b38 uses getter 0xda110 and a signed 32-bit value at +0x10.
JobValue_Bool vtable RVA 0xc46bb8 uses getter 0xda0f0 and one byte at +0x10.
The reader checks expected hashes and concrete runtime vtable types. It exposes a small explicit query list,
not a packaged copy of the whole original defaults resource.

Paused test: Flow_Act=1, Act1_Mission=1, Act1_Stage=2, LCPD_LobbyEntered=2, LCPD_MainframeActive=true.
Old/debug job fields can remain unused; these values are not automatically chapter-completion checks.
Raw probes remain ignored in notes/analysis. See live_paused_key_actor_story.json and live_paused_key_context.json.

## Live key-use comparison

In the same process/save slot, live_key_before_use_ready.json had M02_Dspot_key_item present.
After the user opened the chief-office door, live_chief_office_door_open.json no longer contained that entry.
The four PDA tool entries remained. The active context stayed Default and the selected story values did not change.
This validates removal of this specific attached key after the reported use. It does not independently
read the door-open flag or establish durable ownership, reacquisition or reload behavior.

## Criminal scanner context transition (2026-11-12)

The user stood in the scan aura, then activated criminal scanning and kept it active for capture.
live_criminal_scan_aura_before_activation.json read Default (46); live_criminal_scan_active.json
read PDAScanner (45). Scanner remained unlocked, equipped model stayed COP, attached item definitions
were unchanged. This is the first live-correlated active-scan context transition; it is not a lock or
completion detector, and does not establish the earlier detective interaction context.

## Climbing context (2026-11-12)

While the user reported climbing, live_climbing_reported.json read MechClimbing (55), equipped model COP,
while the global Parkour query was false. Thus that Parkour flag is not a sufficient gate for this observed
climbing interaction. The precise climb subtype (ladder/pipe/ledge/etc.) is not yet specified.
Optional movement gating is a user-requested candidate; entry-condition hooks and progression rules require
separate investigation. An active-context read alone does not implement prevention or item grants.

## Object-carry context (2026-11-12)

While the user reported holding a lifted object, live_object_lifted_reported.json read SuperCarry (141).
Grab, TargetThrow and SuperStrength global queries were all false. The attached-item definition list
contained only the four PDA tools, so that list does not enumerate every physically carried world object.
SuperCarry must not be equated with the SuperStrength unlock based on its name. The object subtype and
interaction-entry gate are not yet established; optional pickup/carry gating is a research candidate only.

## Sandwich handover (2026-11-12)

The user-reported carried sandwich appeared as #ex_238_Sandwich_item in live_sandwich_held.json.
After handover, live_sandwich_handed_over.json no longer contained the entry. The generated prefix
is not a stable AP identifier. This is another specific mission-object presence/removal comparison,
not yet randomized acquisition, permanent possession or a hand-specific detector.

## LEGO assembly context (2026-11-12)

A live actor read returned SpellIt (165), equipped model COP (227). The user then
confirmed that they were assembling a LEGO object at that moment. This establishes
one observed association with ordinary LEGO assembly; coverage across other build
objects and Super Builds remains untested. The context is an action-state observation,
not a verified ability unlock or a working interaction gate.

## Manual death/respawn experiment (2026-11-12)

The user deliberately died during the read-only 100 ms context watch and confirmed
the death afterwards. `death_context_watch_1794449741755180500.jsonl` records
Default (46) -> Jumping (47) -> LandJump (50) -> Jumping (47) ->
DeathContext (63) at 34.520 s -> Default (46) at 36.528 s.
The actor pointer stayed unchanged throughout these samples. Thus pointer replacement
is not a necessary death signal. DeathContext lasted approximately two seconds in
this observation. This establishes one observed death transition, not coverage of
all death causes, scene changes, vehicles or scripted sequences.

A future DeathLink sender should emit once on entry into a verified death state,
not once per polling sample, and suppress echoes of a received DeathLink. No AP
DeathLink messages, health writes or native kill calls have been implemented or
executed by this experiment. Incoming death handling requires separate investigation.
