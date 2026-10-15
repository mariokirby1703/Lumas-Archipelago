# Native events, music popup and Dead Weight ? 2026-10-15

## Implementation and boundaries

All instructions are installed in a separately rebuilt Wii ISO. The original ISO is never modified. Native ABI 2 adds an initialized 128-byte data mailbox and five hooks. The host writes only allowlisted mailbox data, under the existing save/actor policy. No runtime PPC installation or manual Gecko/Riivolution setup is required.

Existing official player containers, legacy JSON migration, music shuffle, five-item HUD, movement gates, Wisp permissions and pickup handling are retained. Known ABI 1 containers are upgraded using current local code, never executable bytes supplied by the container. Old output images are preserved; automatic upgrades use a component-specific output filename. Existing pre-v4 journals omit the newly added disabled trap option from their identity digest.

## PAL native evidence

Supported original: SNCP8P Rev0. main.dol SHA256 `92aefe33b577493b492f8433ca68b90d25d29d2d6f9c85310a6829481281f8a9`; sonic2010_0.cpk SHA256 `58bbf2be97a2f08effb5752bd40eea8a1ba76a18349937a32351624d855651bf`.

| Hook | Original instruction | Purpose |
| --- | --- | --- |
| 8001CE60 | 800400A4 | Gameplay-thread request processing and gameplay-time trap countdown |
| 8001D2B8 | 2C1A0000 | Accepted native death, after ordinary life loss, including Assist deaths |
| 800395B4 | 7C0802A6 | Jump-state rejection before transition callbacks |
| 80125378 | 981E0029 | Successful CRI cue start, excluding failed requests |
| 80056CA0 | 5484103A | Jump input denial for held/pressed/released queries |

CStateDead is registered as state 24 at 80034418..80034464. Forced transition 800338E8 uses the canonical player state machine and ordinary callbacks. CStateDead update 80068728 calls 8020E5EC; the native message constructed by 800571A8/800571C0 has ID 0x5003. Gameplay handler 8001CDB4 dispatches it at 8001D264 and calls life-loss routine 8001BE40. The capture point follows that call and precedes the Assist branch; watching the stage death counter alone would miss Assist deaths.

World-map playback calls 802641A0 -> 802CD644 -> 80126554 -> 80126708 -> 801245EC -> 8012413C -> 801233C0/801237D0 -> 80125310. A successful native virtual cue start at 80125360 reaches 80125378. Descriptor r31 identifies the cue; the bounded inline key is descriptor-32. Only bgm_ names are published. Short bgm_jingle_ events do not produce popups, except the three explicitly supported results clear cues.

Native code lives in audited 12-byte function-alignment slots. Branches and original bytes are validated when building. Each hook preserves GPRs, CR, LR and CTR; the gameplay hook also preserves volatile FPRs around the native transition call. Readers use odd/even sequence publication to avoid torn event data. Revision verification still checks all live patch bytes; page batching and in-place normalization avoid repeatedly copying multi-megabyte text sections.

## DeathLink

A real native death sequence produces one outgoing event, including when host polling misses the animation. Actor disappearance and life-counter differences do not count as proof. Incoming events use standard AP protocol, bounded deduplication and a 30-second safe-gameplay wait. Game-thread request/ACK is consumed before invocation. A remote cycle suppresses echoes until a witnessed death and stable recovery. ACK alone does not release suppression. Expired requests are cancelled; restart recovery cancels stale requests and requires fresh living observations.

Unsafe menus, loading, unavailable owners, transformed players and unsupported special states defer the kill. Super Sonic incoming invocation is not yet verified and is deferred rather than forced through an unknown layout.

Developer commands: `/sonicdeathlinktest` queues a synthetic local receive without broadcasting. `/sonicdeathtest enable`, then `/sonicdeathtest kill`, explicitly enables one local native kill path. Diagnostics expose native sequence, request/ACK, pending deadline, anti-echo state and last action/error.

## Dead Weight

Item ID 847000054. Off/Low/Medium/High weight, default Off. It blocks Jump input and native jump transitions for 30 native gameplay seconds. Menus/loading/death do not consume gameplay time. The policy authenticates the current stage, actor serial, input owner and canonical state machine; it never restores stale physics or actor memory. Each receipt is persisted before publication and confirmed only after guest ACK. Ambiguous interrupted publication is never replayed. Multiple traps wait rather than silently restarting an active duration.

Denied state IDs: 5,6,7,8,9,11,12,18,19,29,30,36,37,39,40,46,47,58,80,106,107,115. These include ordinary, rail, stunt and Spikes transitions; Frenzy additionally uses the generic Jump input gate. Broad live coverage remains required.

## Music popup

Dedicated casts preserve all five AP item rows and native bonus displays. The title resolves the native destination cue through the existing seed audio-leaf mapping and then editable `data/music_display_names.json`. Unknown names have a bounded internal-cue fallback. No persistent music queue/history is used. New tracks replace immediately. Timing is five fully visible seconds, followed by five seconds to zero alpha. Heading and title share the same alpha; item-row alpha is independent. The initial five-second period starts after game-thread ACK. At alpha zero the title string is retained, avoiding an immediate text replacement that bypasses native fading.

User feedback changed the layout to right-aligned above the Red Ring display at the widescreen right edge (630 logical pixels), `NOW PLAYING:` without an icon, with a wider second line. Repeated same-cue starts in the same scene are ignored because live CRI starts also occur at automatic loop boundaries. A different cue, or a new scene/stage epoch, can retrigger it. A same-cue intentional restart inside an unchanged scene cannot yet be distinguished from an automatic loop. Conditional audio-leaf variants are not independently identified beyond the seed mapping. These are explicit remaining limits, not verified features.

## Verification so far

- Real v2 ISO boots without Riivolution/AP-Gecko; full native signature verified in Dolphin.
- World Map successful music event observed: bgm_wmap, native sequence 6. Act cue bgm_stg110_rso also captured; user saw the popup.
- Isolated real MultiServer, two connected clients; new save bound through vanilla New Game and save selection. Public room and its journals were not used.
- Dead Weight delivered through real server: request 1 / ACK 1. User confirmed Jump blocked and restored after the effect.
- Standard incoming DeathLink was also sent by the local AP peer; user confirmed normal death and respawn.
- Natural enemy deaths were captured once. A natural pit death in Tropical Resort Act 2 produced exactly one received standard DeathLink at a separate-process observer (source Luma, cause Sonic died.).
- Synthetic incoming DeathLink: request 1 / ACK 1, native death sequence 0 -> 2. User confirmed exactly one ordinary death and respawn; no repeated death.
- Score Reset delivered through real server: user reported 33400 -> 0 and red Trap HUD colour.
- Focused native/model tests: 70 passed; additional patch/container/resource/HUD tests: 30 passed (overlapping HUD tests).
- Initial full suite: 17946 passed, 122 failed. Isolated HEAD baseline: 17727 passed, 143 skipped, 122 failed. The initial identifier comparison incorrectly read UTF-16 PowerShell logs; a proper decode found five differences in either direction. The new restart policy required updating one old DeathLink expectation, automatic developer-result logging was returned to debug level, and three private-capture fixtures needed the existing spawn-refresh status included. Those affected tests now pass (52-test focused run). Private-asset omissions prevent treating the copied baseline as a fully equivalent environment. Final full-suite results are recorded separately below; the suite is not wholly green.

## Remaining live matrix ? do not claim complete

DeathLink: drowning, Game Land and Assist, Wisp/Super deferral, map/loading expiry, reconnect/restart and no-echo recovery across these cases.

Dead Weight: pause timing measured, rails/stunts/Spikes/Frenzy, death/respawn, stage changes, reconnect and repeated receipts live. Normal Jump alone is confirmed.

Music: revised v4 position/width, loop suppression, simultaneous smooth fade, new Game Land-selection and results resources, real randomized heard-track comparison, boss/Game Land/Wisp/in-Act changes and scene reconnect. Original request wants actual conditional playback identities; not proven yet.

Production DeathLink and Dead Weight generation remain gated by versions.json live_validation flags until the relevant safety matrix is complete. Music popup also remains marked unverified in that report. Do not distribute private ISO/CPK/DOL dumps or test journals. Release package contains only code, metadata and locally applied builder instructions.

## Follow-up UI correction

V3 user feedback showed that the 640-pixel right edge was insufficient for widescreen and the title vanished abruptly. V4 live feedback showed 830 was outside the viewport. The corrected client uses the 630-pixel right edge, places the two lines above the Red Rings, and preserves the title while alpha reaches zero. Music publication runs before slow guarded owner reconfiguration. Game Land selection (`ui_title_multi`, `multi_bg`) and results (`ui_result`, `result`) have dedicated appended resources, with exact original-record preservation and all original animations retained. Discovery accepts the verified dictionary sizes 93 and 95 respectively. Tests verify both original resource animations and casts remain unchanged. The initial production-layout live test is still pending.

Final complete suite after the behavior/fixture corrections: **17956 passed, 117 failed**. Properly decoded failure identifiers introduce none relative to the copied HEAD baseline; five baseline failures concern code/asset packaging differences in that isolated copy. Known repository failures remain and are not presented as a green suite. Subsequent changes only adjust the right-anchor constant and its focused assertion.
