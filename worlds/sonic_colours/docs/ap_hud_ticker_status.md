# AP HUD ticker implementation status (2026-10-14)

## Scope and preserved behavior

Branch Sonic-Colours-Wii-AP, HEAD 078e1189 inspected before edits. Existing work and commits retained. No executable RAM writes, asset modifications, Gecko arena expansion, or bonus-score mutations performed.
The supplied CODEX_START_HERE.md, RESEARCH_DE.md and CODEX_PREVIOUS_PLAN.md were read in full; their source material is retained in notes/ap_hud_handoff.

## Phase A: blocked native renderer

No original CPK was found in the workspace or Downloads top-level; verify_original_assets.py therefore could not be executed against original bytes. The ZIP contains research and tools, not the original UI resources.
The documented info_bonus word_bonus is a sprite, num_bonus has only numerical glyphs. common_text is verified only in another asset by the supplied inventory. A live gameplay font, its texture owner, and two independent casts have not been proved.
No replacement of the native bonus UI is implemented. No visible Dolphin text or 30-second overlay success is claimed.
Needed: original SHA-256-matching CPK; read-only bonus-owner probe at PAL 80111230/80111294; scene/cast/font/atlas ownership; separately instantiated two-line layout; typed 805E6888 call proof; safe draw-thread lifecycle and real buffer/glyph metrics. Then native PoC and 30-second bonus coexistence test, Wisp/death/pause/stage transitions and ten map changes.

## Phase B: implemented event pipeline

client/ap_hud_ticker.py: seed-journal durable receipt highwater and sent identity deduplication; bounded 32-event FIFO with oldest-pending overflow accounting; five-second dwell; last event remains indefinitely; hidden scenes pause scheduling; native glyph-safe transliteration and width clipping accepting only provided verified glyph metrics.
client.py handles Sent only from PrintJSON ItemSend from our slot to another slot, resolves item names in the recipient slot; Received only from synchronized ReceivedItems, uses sender player and own item lookup. First index=0 snapshot establishes silent history baseline; subsequent unseen receipt indices are queued. Local test inventory commands and LocationChecks do not generate ticker events. A fresh first-ever history snapshot cannot distinguish pre-connection rewards from history; this inherent ambiguity is explicitly treated as history, not fabricated live notifications.
ap_item_hud defaults Off; old slot data normalizes missing option to Off. /sonichud reports hud_ready/font_ready/owner_verified false with the specific blocked reason, event count, queue and current text.
Events are recorded while rendering is unavailable, but the runtime intentionally does not consume display dwell or claim native writes. Native renderer remains unimplemented and disabled. Local text-test mutation is not exposed without a verified renderer.

## Phase C and World Map

Offline event/scheduling/encoding/dedup/budget tests pass. Real two-player Sent/Received rendering, GPU/font buffers, bonus/scoring coexistence, memory leaks and native scene restoration remain unverified.
Live read-only Dolphin was available on a previously loaded Tropical Resort map: Act statuses 4,4,2,2,2,2,1; no initial-load reproduction was available. Existing project_permissions writes availability flags and node statuses; model and path setup occurs during native initialization (8026892C, 80268BA0, 802693AC). The initial-map issue is NOT fixed by this change. Writing the node +108 existence flag is not a verified refresh and was intentionally not used. Next required work: native map-owner update entry capable of rebuilding only affected node visuals/path caches, verified first-load snapshot and full Gecko budget check.

## Delivery

Experimental event pipeline only. No new HUD Gecko code is supplied. Keep ap_item_hud Off for normal play until native rendering is implemented. Existing Gecko profile remains valid. No completion commit was made: the requested visible native HUD acceptance criterion has not been achieved, and the workspace contains pre-existing changes which were not staged wholesale.

## Live bonus-owner evidence, subsequent probe

Paused Tropical Resort Act 1 with Grind Bonus 3000: verified live actor vtable 80764440, update vtable+40=8010DE38, bonus scene handle actor+3A4 (reference at +3A8), scene layer vtable 807ABC40. Layer+0C points to an 18-cast dictionary at layout+30 with num_bonus=(group0,cast7) and word_bonus=(group0,cast8). Native score entry actor+3B8 was 3000. Read-only owner and pane snapshots saved in build/ap_hud_probe. client/ap_hud_native.py resolves these pointers fresh per probe; /sonichud reports owner_verified independently from font_ready and hud_ready. No UI writes or alphabetic rendering were performed.

## Live movie subtitle path

The options actors remain resident during movie playback; their presence does not classify the visible scene. Separate actor vtable 8077E880 has movie controller at actor+50 with reverse owner at controller+0. Controller state+1C=2 (playing), resource event/ev110_seq.arc, subtitle XTB manager+14, active subtitle object+18. Subtitle object+5C points to text layout vtable 80761960; live object bytes include UTF-16-BE Welcome to / Eggman... . Static movie code 802F4EE4 processes subtitle timing; 802F4FB4 resolves XTB text through 800F64D8 and applies subtitle placement/reveal through 800F6854. This is a separate native message renderer, not a CSD num_bonus font cast. Evidence: build/ap_hud_probe/movie_subtitle_owner.json and subtitle_text_object.bin. Font atlas ownership, glyph coverage and retaining this renderer in a normal gameplay scene remain unresolved. No mutation performed.


## 2026-10-14: new info_2 handoff, implementation in progress

The complete new handoff is retained in `notes/ap_hud_live_handoff`.
Its corrected resource evidence includes `ui_soft_keyboard.tls` (108864 bytes,
4 textures); the alphabet is not automatically available in gameplay.
`info_2` is the preferred candidate, not yet a live-validated overlay parent.

Implemented in this step:
- Non-consuming `Ticker.candidate`, matching `published` acknowledgement and
  `elapsed_visible` dwell accounting. Existing tick API remains for compatibility;
  production runtime must use the acknowledgement API once a renderer exists.
- Bounded two-line, 128-byte-per-line mailbox wire format and odd/data/even
  publication order. This module deliberately contains no guessed RAM address.
- `tools/prepare_hud_assets.py` performs original CPK hash/preflight validation
  before extracting four private resource inputs into a NEW directory. It never
  overwrites the original. This is preparation, NOT a GNCP/TLS overlay builder.
- 13 ticker/mailbox tests pass; preparation tool syntax checked.

Still required: original CPK path, actual TLS/relocation inspection and rewriter,
GNCP font/cast extension, authenticated info_2 owner, game-thread setter and
native ACK, runtime/write-policy integration and all visible Dolphin validation.
The current complete Gecko profile uses 3256/3256 bytes; a HUD publisher cannot
be appended without verified space savings or another verified loader strategy.
No font_ready/hud_ready claim, no RAM mutation, no Nintendo assets committed,
no release build or completion commit from this partial step.

Preparation command (from repo root):
```
.venv/Scripts/python.exe worlds/sonic_colours/tools/prepare_hud_assets.py ORIGINAL_CPK build/ap_hud_assets
```
The source must match SHA256
`58bbf2be97a2f08effb5752bd40eea8a1ba76a18349937a32351624d855651bf`.


## 2026-10-14: original resources supplied; static asset PoC built

Original private CPK was found under `notes/memdumps_and_more` and matched the
expected SHA256. Assets were extracted under ignored `build/ap_hud_assets`.
The read-only Dolphin attempt returned `emulation_not_running`.

New tools `hud_tpl.py`, `hud_gncp.py`, `build_hud_overlay.py` build a separate
static two-line overlay archive. TLS source atlas 3 (312x192, IA4, 59904 bytes)
imports at target index 12. Existing twelve table entries/pixels are preserved.
GNCP append-only rewrite adds font `ap_common_text`, 77 glyph mappings and UV
entries, per-texture normalized dimensions, third score-scene group with two
font casts, dictionary names, empty animation tracks, and rebuilt NOF0/header.
Existing score cast offsets/records and bonus scene records are preserved.
Positions are experimental and require visual QA; rendering is NOT verified.
All 22 cockpit archive TOC aliases have identical original bytes and receive the
same replacement. U8 and CPK roundtrips verify all replacements and unchanged
other U8 members. Original CPK is never overwritten. 15 targeted tests passed,
including the actual privately extracted GNCP, deterministic rewrite, TPL
bounds, queue acknowledgement and mailbox protocol.

Artifacts:
- `build/sonic2010_0_ap_hud_poc.cpk`
- `build/sonic2010_0_ap_hud_poc.xml` (PAL Rev0 only, default disabled)
- `build/sonic2010_0_ap_hud_poc.cpk.hud.json`

Rebuild into a NEW output filename:
```
.venv/Scripts/python.exe worlds/sonic_colours/tools/build_hud_overlay.py ORIGINAL_CPK NEW_OUTPUT.cpk
```
Load the generated XML alongside the generated CPK via Dolphin's Start with
Riivolution Patches and enable Static two-line HUD PoC. Expected static strings:
`Sent Test Item` and `to SM64 Player`. No APWorld reinstall is needed for this
asset-only experiment. Existing Gecko profile remains unchanged. Do not combine
this full CPK replacement with another full CPK music replacement; a combined
resource/music build still needs implementation.

Sources used for layout cross-check:
- https://github.com/tge-was-taken/010-Editor-Templates/blob/master/templates/sonic_xncp_yncp.bt
- https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/DiscIO/RiivolutionParser.cpp
- https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/DiscIO/RiivolutionPatcher.cpp

NEXT: visible static PoC and live info_2 ownership, then native setter/publisher
and integration. No game-thread renderer installed yet; no hud_ready claim.


## Static PoC v1 failed live; v2 dictionary ordering repair

User observed no text and Dolphin invalid read 0x000000AA at PC 0x805E2808.
PAL disassembly proves 805DE874 performs binary search (803757C0) on font IDs
and returns -1 on missing name. 805E2CE8 uses that index without rejecting -1,
selecting the font-table record eight bytes before the table. The v1 appended
font ID `ap_common_text` after `num`, `num_s`, violating sorted dictionary order.
The preceding bytes were the last added glyph mapping (z, subimage index 170),
so this selected mapping pointer 170 = 0xAA. 805E2808 is the glyph comparator
used by the next bsearch at 805E2E4C. This matches the exact invalid address.

Repair: sort font-ID and cast-name dictionaries, keeping every original font
index and cast group/index unchanged. Regression checks require sorted names
and successful binary lookup for every entry. Asset tests: 2 passed. Rebuilt
all 22 aliases into NEW `build/sonic2010_0_ap_hud_poc_v2.cpk`, with matching
`build/sonic2010_0_ap_hud_poc_v2.xml`. v1 is superseded and must stay disabled.
v2 is still pending visible Dolphin validation; no ready claim.


## v2 visible but clipped; v3 placement repair

User screenshot confirms alphabet rendering in a normal Act after v2, with
oversized cyan text clipped at upper-left. It does not confirm both full lines
or the required 30-second lifetime. Static/native inspection identified the
keyboard font cast's flags 0x18: 805E3198 delegates position to 805E06B8 and its
805E08E8 pixel-coordinate fallback, using record +0x68/+0x6C. These remained
zero in v2, so CastInfo normalized translation alone did not move the text.

v3 sets pixel positions (40,340) and (40,362) on the 640x480 UI canvas, keeps
normalized positions consistent, sets scale 0.5 and all colour/gradient words
to FFFFFFFF. Tests assert the actual pixel fields, scale and colour. Asset tests
2 passed; archive rebuilt as `build/sonic2010_0_ap_hud_poc_v3.cpk` with matching
XML. Placement and full-line visibility still require user Dolphin validation.


## v4: compact glyphs and five-message panel

User confirmed v3 arrives, but glyphs are widely spaced and requested five
messages in the area below time and above boost. Source common_text glyphs
occupy uniform 24-pixel-wide cells. New UVs crop transparent IA4 columns with
one-pixel padding, preserve vertical bounds and the original atlas pixels,
and give space a seven-pixel advance. IA4 high-nibble alpha verified against
Dolphin TextureDecoder_Generic.cpp. Native spacing correction is zeroed.

Static panel now has ten font casts (five two-line messages), original thirteen
score casts retained; score scene dictionary count23, third group count10.
Pixel coordinates x96, y130 + message*40 + line*17 on the 640x480 UI canvas,
scale0.45, white. Sample wording Received ... / from ... and Sent ... / to ... .
No original bonus or score animations removed. Empty new animation tracks
match all ten casts. New artifact `build/sonic2010_0_ap_hud_poc_v4.cpk` and XML.
Older PoC XMLs must be disabled. Live compact spacing/placement is pending.

Ticker now stores the last five acknowledged events and previews newest-first
panel content without consuming pending entries. This is scheduler preparation;
the real native setter/ACK publisher and five-message runtime integration remain
unimplemented. No actual AP item render claim. 16 asset/ticker/mailbox tests pass.


## v4 rejected by live render; diagnostic isolation pending

User reports invalid read 0x3F2DF2FB, PC805E0E4C, when HUD first appears at Act
entry. Static disassembly: 805E3C08 retrieves global renderer at 808512D0;
805E0E3C loads its vtable; 805E0E4C reads virtual slot+1C. Therefore this error
is an invalid renderer object/vtable, NOT the prior missing-font comparator.
The value minus1C is 3F2DF2DF, an atlas UV float introduced by column cropping.
This is a clue, not enough evidence to establish the corruption path.
The read-only DME attempt found no hooked instance and yielded no live pointers.
Do not claim a fix. v4 remains superseded/disabled for normal play.

Builder now supports one-message and untrimmed-cell diagnostic variants.
Generated `build/sonic2010_0_ap_hud_diag_two_compact.cpk` + XML has only TWO
casts but compact UVs/new positions, isolating text changes from the ten-cast
extension. User must test this variant next and keep Dolphin open on failure.
Asset tests2 passed; offline structure checks do not establish runtime safety.


## Five-block user mockup / separate-group experiment

User supplied desired five vertically stacked two-line blocks, retaining the
confirmed compact two-line font. One-message compact diagnostic was confirmed
visually working; this excludes glyph trimming alone as sufficient cause of
v4's ten-cast failure. Exact corruption path remains unresolved.

New experiment uses FIVE separate two-cast groups instead of one ten-cast
group. Each hierarchy is the live-tested (-1,1,-1,-1) shape. Scene group count7,
cast dictionary23; animation group tables expanded consistently to7 with empty
tracks for each pair; animation2 group table has five null entries. Existing
native groups/casts unchanged. Positions and size match the prior five-block
layout (x96, y130, 40px block pitch, 17px internal line pitch, scale0.45).
Artifact `build/sonic2010_0_ap_hud_five_groups.cpk` and matching XML. This is an
experiment, NOT a proven fix or active AP renderer. Structure tests2 passed,
CPK/U8 roundtrip validated. Next required: user live five-block render test,
followed by native publisher and real AP item integration.


## Live cause established: shared 128-quad renderer overflow

Live warning-state dump retained in build/ap_hud_probe/renderer_failure.json.
808512D0 points to native static renderer80853B00. Its vtable word was replaced
by3F2DF2DF and adjacent fields contain glyph vertex data. Native805ECB90 initializes
this renderer's vtable to807ABDF8. Original vtable slot1C points805EC6E0.
That writer appends80bytes per quad at808512E0 + counter*80, with counter80853AE0,
without capacity check. (80853AE0-808512E0)/80 =128. Quad129 writes across the
counter and renderer storage. This explains exact vtable corruption. Splitting
font groups cannot avoid the shared buffer limit.

New client/hud_renderer_batch.py replaces the original120-byte quad method plus
its44-byte PRIVATE vertex-copy helper with an exact164-byte boot-time Riivolution
patch. It flushes existing quads using805EC784 before appending when count>=128,
resets count, and preserves vertex order0,2,3,1 and r29-r31/LR/stack. No new code
arena, no direct host executable writes. XML gates the complete original164bytes.
verify_revision recognizes ONLY the complete exact replacement, normalizing it
for PAL hashing; other edits still fail. Existing Gecko bytes are unchanged.

Actual PPC tests cover count0/127/128, volatile clobbering by native flush,
word-for-word vertex copy, counter and renderer boundary, ABI and exact-match
normalization. Asset/ticker/mailbox/batch targeted tests20 passed.
New private build/sonic2010_0_ap_hud_bounded.cpk and matching XML combine five
message groups with this bounded renderer patch. LIVE validation pending.
New build/apworlds/sonic_colours.apworld includes revision recognition, SHA256
2f324b67e595beaed994fbd209fce255c54d030f263150f51c582592bc7aa3fe.
Restart emulation to discard corrupted live renderer before testing; only new
bounded XML should be enabled. Still static sample messages; AP publisher pending.


## Styled panel requested after bounded five-block live confirmation

User screenshot confirms five blocks render with the bounded native quad writer.
New static experiment `build/sonic2010_0_ap_hud_styled.cpk` + XML: x96, basey140
(10px lower), 40px block pitch, left alignment through zero left font-corner X.
Each message separates white Received/Sent prefix, coloured item name and white
from/to player line. Prefix advance derives from cropped source glyph UV metrics.
Progression AF70FF, useful305BD8, filler64C8FF, trapF05252; RGBA alphaFF.
Four black copies at cardinal offsets0.8px form a thin outline per text segment;
15casts/message, five groups, original13casts retained. Native bounded writer
is required; graphics/performance and coloured alignment need live validation.

Ticker Received/Sent now retain AP flags; five acknowledged entries have durable
wall-clock publication timestamps and expire120seconds after publication. New
entries evict beyond newest5. Reconnect does not reset timestamps. Classification
helper selects trap, progression, useful, filler in that precedence. This remains
host preparation, not an integrated native AP publisher. STATIC SAMPLES DO NOT
EXPIRE. Asset/ticker/mailbox/batch tests22 passed. Native real AP publisher and
timer integration still required; do not claim this static panel completes HUD.


## Styled panel horizontal alignment

User confirmed styled five-message panel with colours and outline live. Requested
left edge match boost/top HUD. Common X origin changed96->50 UI pixels, moving
all prefixes, items, player lines and outlines46 UI pixels left. Other layout
parameters unchanged. New private artifact build/sonic2010_0_ap_hud_styled_left.cpk
and XML; builder roundtrip completed. Native publisher still pending.


## World/Area Map static overlay extension

Original CPK inspection: both map presentations share ui_worldmap_e.arc resources
ui_worldmap.gncp/TLS. info_1 has3groups,21casts,1animation and life/rank/ring HUD.
TLS13textures; added alphabet textureindex13, dimensional table14 entries.
Generalized overlay builder supports original parent group/cast/texture counts,
keeps all native map casts intact and appends5 message groups with empty tracks.
Base y176, x50, same styling; last player line y353 above native controls.
Builder --maps creates combined gameplay+map CPK in one atomic copy; every alias
validated original-identical and rewritten, unaffected U8 members byte-identical.
Artifact build/sonic2010_0_ap_hud_maps.cpk and matchingXML. Original map rank/ring
cast identity preservation and actual map layout tested; asset/batch tests7 pass.
English UI resources patched (other language variants unchanged). World/Area Map
visible lifetime/placement and bonus/controller coexistence require live test.
Still STATIC samples, real AP publisher remains open.


## AP-connected publisher implemented; first live publication pending

World/Area Map styled static HUD was confirmed by user. Added ap_hud_publisher.py
(native game-thread wrapper lookup, String/Colour setter, positioning, reference
release and ACK), ap_hud_connected.py (current scene owner/75 mailboxes, exact
data-write transaction, generation barrier, lifecycle restoration), WritePolicy
hud_mailbox allowlist, Runtime polling, persistent /sonichud on/off and isolated
/sonichud test. True Sent/Received handlers now retain AP flags. Existing server
option remains Off-default and no native gameplay/progress fields are written.

Boot publisher uses audited ordinary C++ function-alignment padding after BLR
and before STWU; no exception-vector padding, new low-memory arena or host code
writes. All original code/data pointer and direct branch references audited.
Native full plan and bounded renderer guard must match for revision normalization.
PPC tests execute emitted instructions and mock native calls; test even/odd/old
generations, owner-class rejection, wrapper/pane validation, reference cleanup,
register/stack/FPR preservation. Host tests ensure no queue consumption until
all native ACKs and check expiry/Off. Connected GNCP uses immutable blank source
strings plus separate bounded resource mailboxes to avoid setter equality alias.

34 targeted HUD and Gecko-budget tests passed. Read-only live Grand Map owner
resolved as actor90B508C0/vt80777000, scene handle90B50960, layer90B530C0,96casts;
recorded in build/ap_hud_probe/map_and_gameplay_handles.json. This is NOT the
new native publisher's live proof. Documentation: docs/ap_hud_connected.md.

Release candidates: build/sonic2010_0_ap_hud_ap_v1.cpk and sibling XML;
build/apworlds/sonic_colours.apworld (current build manifest identifies the package).
Native live test needed after installing new APWorld and restarting emulation
with ONLY new AP-connected XML; existing Gecko profile unchanged. /sonichud on,
then /sonichud test once font_ready. Next: real Sent/Received, two-minute timeout,
menu/Act transitions and 100 updates/performance validation. No completion commit
or claim of live-connected text until these are validated.
