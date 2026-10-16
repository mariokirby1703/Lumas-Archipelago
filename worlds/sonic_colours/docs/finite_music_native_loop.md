# Finite-song native replay, 2026-10-16

The user audibly tested both bgm_sys_op (Reach for the Stars) and bgm_sys_end
(Speak with Your Heart) as Tropical Resort stage music. Both played and neither
looped with CSB audio-leaf substitution alone. These observations are recorded
in finite_music_live_audition.json. Neither result is a loop success.

The new fallback hooks the native channel update at 80125004, after its status
query. It admits stopped status 4 only, with a positive native owner count,
a previously successful cue start, no pending stop/fade/pause flags, and an
exact match between the channel descriptor and the authenticated loop policy.
It calls the original 80125310 cue-start wrapper on that existing player and
descriptor, on the game's own update thread. Full volatile floating-point and
integer state, CR, LR and CTR are saved and restored. There is no host duration
timer, audio re-encoding, AAX modification, or foreign-thread engine call.

Host publication uses the reserved event-mailbox word 104. Before each change,
the write policy independently verifies the native executable/mailbox and the
resident PAL CSB bank. It proves the current cue is an eligible looping
**destination** whose complete leaf vector uses exactly one of the two finite
songs. Original opening and credits cue destinations cannot receive this
policy. A stop, fade, pause, owner release, different cue, unknown bank, or
unknown native version prevents replay. Normal scene-specific stop behavior
continues to own the channel. Song restarts use actual stopped status rather
than an estimated track duration.

Code uses additional 12-byte zero alignment sites recorded in
native_music_loop_sites.json: each follows a blr, precedes a directly referenced
function entry, has no direct branch into its padding, and does not overlap an
existing patch. Every replacement validates the original zero bytes against the
SHA-verified original DOL; the native plan rejects all patch overlap.

Validation so far: 191 focused native-event, music-bank and seed-patch tests
passed. Executed PPC tests cover stopped, playing, paused, error, disabled,
unowned, not-started, stopping, mismatched cue and missing descriptor contexts,
plus register/FPR preservation. Resident-policy tests cover both songs, ordinary
music, unknown IDs and original opening/credits exclusion. The real CRI start
implementation is not executed by those unit tests.

Pending live acceptance: boot the new native_music_loop.iso; audition each song
past its full duration and hear the restart; leave the Act during playback and
near EOF; pause near EOF; repeat in a map and Game Land; confirm original opening
and credits complete normally. Native stopped-status semantics and CRI replay
behavior need this live confirmation. A full-song restart may have a short gap;
no seamless musical loop is claimed. Release-loop validation remains false and
the default production shuffle still excludes finite songs until acceptance.

No HUD/music-popup visual or display-name changes are part of this fallback.


## First native audition failed; V2 latch

The first native test failed live: the start sequence had reached 2868 while
still in the same Act. The player can remain stopped/preparing immediately
after Start, so stopped status alone caused repeated restart requests. The
trial was disabled. This is a failed live test, not a loop success.

V2 uses bit 16 of policy word 104 as a guest-owned armed latch. It is set only
once the same eligible, owned channel reports playing/paused status 2/3. A
stopped-state replay consumes that latch BEFORE calling Start. Until actual
playback is seen again, further stopped/preparing frames cannot issue another
request. Host publication preserves the upper latch bits for the same cue and
resets them when eligibility changes. The two additional PPC regression cases
exercise the unarmed end and repeated 4/1/4 preparing/stopped sequence. The
focused suite now has 193 passing cases. V2 remains pending a live audition.


## V2 live failure: cached identical cue

After the user reported no restart, native music_sequence changed from 14 to
16, policy was 0x000003e9 (latch consumed), the channel retained one owner and
flags 0001. Thus V2 issued one Start and did not storm. Static tracing of the
actual player's vtable (807ABFD4) led to 80600414: at 80600470..80600494 the engine
compares its cached cue/bank and returns at 80600588 if identical, even when the
previous stream has ended. A successful request boundary is not proof of new
audible playback.

V3 therefore calls the original channel Stop wrapper 801251EC before its Start
wrapper 80125310, with the descriptor retained in a nonvolatile saved register.
Stop resolves through 805FDD04, releases the player instance and clears its
cached instance pointer at 805FDD70. The next Start cannot take the same-instance
early return. The latch is still consumed before both calls. PPC tests assert
the exact Stop/Start order and argument/CPU state preservation. All 193 focused
cases pass; V3's audible restart remains unverified until a real full-song test.


## V3 live failure: Prepare is not Play

The user again heard no repeat. After the attempt, the channel had owner count
1, flags 0001, consumed latch, and underlying player status 3 with a newly
allocated instance. Further original caller tracing showed that 80125310 is
Prepare: handle assignment calls it at 80123830. A distinct handle Play request
calls 80125390 at 80123714. The latter sets pending Play, and the normal channel
update dispatches the actual CRI start method. The existing MUSIC_SEQ boundary
therefore records a successful cue preparation; it cannot certify audible
playback or restart, and is now documented accordingly without changing its ABI.

V4 invokes Stop -> Prepare -> Play (zero fade duration) on the same owned
channel. Tests assert all three calls in order and preservation of integer,
FPR, CR, LR and CTR state. The ended/preparing latch regression remains in
place. The 193 focused tests pass; no successful audible loop is claimed.


## V4 first audible success

The user confirmed "yay es funktioniert!" during the Reach for the Stars
stage audition on native_music_loop_v4.iso. This is the first confirmed audible
full-song restart. It verifies this donor/destination and the Stop/Prepare/Play
fallback in that live test; it does not certify the second song, repeated loops,
scene changes, or original opening/credits completion. Production validation
flags and the ordinary shuffle pool remain unchanged pending those tests.


## V4 second donor success

The user also confirmed "funktioniert" for Speak with Your Heart in the same
stage audition. Both requested finite songs now have a user-confirmed audible
full-song restart through Stop/Prepare/Play. This closes the two donor playback
checks, not the broader scene-transition/cutscene acceptance matrix. Original
opening/credits destination exclusion is covered by unit tests; their natural
completion has not been live witnessed in this pass. Default shuffle inclusion
remains a separate versioned mapping change, with legacy mappings preserved.
