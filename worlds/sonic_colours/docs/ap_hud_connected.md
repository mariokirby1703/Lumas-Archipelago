# AP HUD connection (PAL Rev0, English UI)

The styled five-message resource overlay is live-confirmed on gameplay, World
Map and Area Map. The AP-connected publisher is implemented and tested offline;
The first connected live test crashed at `0x805DE394` (read address 3): cast
lookup received a reference handle instead of the unwrapped scene layer.
The v2 publisher corrects r4 and has 35 passing offline checks, including the
original native caller's ABI. Its corrected setter/ACK path needs a live retest.

## Install the connected version

1. Install the freshly built `build/apworlds/sonic_colours.apworld` and restart
   the Sonic client. Existing seeds are supported.
2. Restart Dolphin emulation. Load only
   `build/sonic2010_0_ap_hud_ap_v4.xml` through Start with Riivolution Patches,
   enable AP Item HUD. Keep `sonic2010_0_ap_hud_ap_v1.cpk` beside it; the assets
   are unchanged. Disable older HUD XMLs.
3. Retain the existing combined movement/capsule Gecko profile. The publisher
   does not consume or enlarge the Gecko arena.
4. Connect the client. The HUD is always enabled with the native patch installed,
   including existing seeds with the old option set to Off. Old local Off
   overrides are ignored.
5. In an Act or map, run `/sonichud`. Once native casts are available,
   `/sonichud test` submits a clearly named local HUD preview. It sends no AP
   packets, items or checks. Then test a real incoming item and a real sent item.

The connected assets start blank; there are no static sample messages. A missing publisher or invalid owner never consumes
queued events. First-ever ReceivedItems history remains a silent baseline;
subsequent receipts and real ItemSend packets populate the panel.
The ordered connection history barrier also initializes an omitted empty history,
so the first live receipt (including an item found for oneself) is displayed.
The v2 native publisher and local preview are now user-confirmed in gameplay;
real event delivery after this baseline correction still requires live retesting.

## Behavior

The v4 publisher compares each cast's existing text, position and override
colour. Unchanged casts keep drawing; alpha-only updates do not run the text
setter, rebuild transforms or skip a draw. During the final five seconds, each
cast converges down by at most one alpha unit per draw (about 4.25 seconds at
60 Hz), independently of host update timing. Foreground and outline receive
the same target alpha. This corrects v3's panel-wide blinking; live smoothness
and concurrent-message regression testing remain pending.

Newest messages appear first, up to five two-line entries. Each acknowledged
entry expires after 120 wall-clock seconds or eviction by five newer entries.
Reconnect retains timestamps. Names use the recipient game's item lookup for
Sent; player aliases come from AP. Local movement `/give` commands are not AP
ReceivedItems and do not produce HUD item events.

Only item names are coloured: progression purple, useful dark blue, filler light
blue, traps red. Prefixes and player names remain white; the black four-direction
outline and confirmed positions are retained. Strings are normalized to the
77-glyph font, fitted using extracted metrics and bounded to 127 ASCII bytes.

## Native implementation and proof

`ap_hud_publisher.py` hooks the font draw path at 805E0DDC. Its small blocks are
installed at boot by exact-original Riivolution patches in audited ordinary
function-alignment gaps. These are after a BLR and before a STWU, outside low
memory/exception vectors, with no original direct branch or pointer references.
The existing functions remain unchanged. All blocks and the bounded 128-quad
renderer must match before the client accepts this optional PAL revision.

Each AP cast has a resource-owned bounded mailbox, including the native cast
name and shared generation controller. Source font text stays an immutable
blank; mailboxes are separate, so the native setter's equality check cannot
mistake the pending text for an already installed buffer.

The host resolves a current actor's native scene handle and all 75 named casts,
validates scene/layout/controller anchors and opens an exact-address data-only
transaction. It publishes odd generation, all data, then even generation. No
host executable-memory writes or manually allocated native strings are used.

The guest checks marker, generation, scene class, original cast and current
runtime pane; obtains a real native wrapper through 805EB154; calls 805E6888
and 805E6734; updates native positioning; releases the temporary reference with
805E9C68; acknowledges only the same complete generation. Register, stack,
CR/LR/CTR/XER and volatile floating-register state are preserved. The host commits
display history only when every cast acknowledges the generation.

The Grand World Map actor/scene-handle chain was resolved live in
`build/ap_hud_probe/map_and_gameplay_handles.json`. This was a read-only probe of
the confirmed static overlay, not a live publisher test.

## Remaining live validation

- Nonempty local preview and all 75 native acknowledgements.
- Real Sent and Received, including a recipient from another game.
- Two-minute expiration, six-item eviction, Off, reconnect, death and pause.
- Gameplay/World Map/Area Map transitions and owner restoration.
- Native bonus/score coexistence, 100 text updates and memory/framerate checks.

## Rebuild owned resources

From repo root, into a **new** output filename:

```
.venv/Scripts/python.exe worlds/sonic_colours/tools/build_hud_overlay.py ORIGINAL_CPK NEW_OUTPUT.cpk --maps --ap-connected
```

The original CPK is SHA256-gated and never overwritten. All cockpit/map archive
aliases are rewritten consistently and re-extracted for roundtrip checks.
Original proprietary resources remain local and ignored by Git. The builder's
parser/preflight helpers are included under tools, without requiring ignored
research notes. A full CPK music replacement must be combined in a single build;
do not enable two different full CPK replacements at once.
