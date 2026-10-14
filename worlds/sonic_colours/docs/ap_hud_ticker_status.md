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
