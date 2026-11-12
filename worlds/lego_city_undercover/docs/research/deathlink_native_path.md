# Native death research, 2026-11-12

Applies only to the executable SHA-256 gated by bridge/diagnose.py. All RVAs below
were derived from local static disassembly; no native calls or memory writes were
performed. This is not an implemented DeathLink receiver.

## Health

The GetHealth name getter is RVA 0x7609f0. Its action descriptor at file offset
0xd39620 points to the typed method 0x7611c0 (the preceding 0x4a1e80 is a generic
dispatcher). It converts the character interface to actor by subtracting 0x10,
then calls 0x66a380, which reads uint8 actor+0x943.

SetHealth's getter is 0x760a50, descriptor file offset 0xd39788, typed method
0x761490. Its assignment/add/subtract branches eventually call 0x66f7b0, a plain
byte store to actor+0x943. The related limit getter 0x66a6f0 reads actor+0x942;
0x66fca0 writes that byte. Setting health alone has not been shown to enter the
native death/respawn flow. Do not describe it as a verified kill operation.

The read-only watcher now records both bytes. At observation time both were 4,
and the player context was Default (46). Damage/health correlation remains untested.

## Native Kill action

The Kill name getter is RVA 0x760a30. The action descriptor at file offset
0xd39748 points to typed method 0x761390. For a character it obtains the actor
pointer and branches on actor+0x3e3. For a player (value other than 0xff), it calls:

```
RVA 0x79ad00
RCX = actor
EDX = 3
R8  = 0
R9D = 1
stack args 5, 6, 7 = 0
```

These are the observed caller arguments, not names assigned to unknown parameters.
The nonplayer branch instead calls 0x6687b0 and 0x7976d0. Avoid invoking the whole
script wrapper without a genuine script execution context.

0x79ad00 can propagate to an associated character and calls the action-state
operation 0x66fcb0, with fallback 0x6709c0. It populates an action-state structure
and can update associated entity state. These operations have engine-owned state
and lifetime dependencies. An arbitrary remote-thread call has not been verified.
A game-thread command bridge and actor lifetime checks are still required before
the controlled incoming-death experiment. Changing the context index directly is
not a substitute for this native path.

## Detection and future validation

The previous manual death produced Jumping -> DeathContext (63) -> Default on the
same actor pointer. The read-only log captured about two seconds in DeathContext.
`tools/watch_player_context.py --seconds 180` records context and health changes;
the duration is bounded and executable hash checked.

After a game-thread bridge exists, a single native Kill request must be checked
for DeathContext entry, normal breakup/respawn, return of control, and absence of
repeated kills. A received DeathLink must suppress the outgoing echo. Vehicle,
cutscene, loading and menu behavior need separate handling. No AP message has been
sent and no incoming DeathLink has been simulated so far.
