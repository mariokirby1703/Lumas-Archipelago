# Synchronization performance — 2026-10-17

The native-memory loop stays single-owner and synchronous between explicit
AP checkpoints. No background worker races socket callbacks, journals,
scene changes or receipt delivery. Socket ReceivedItems callbacks persist
the authenticated inventory but leave native permission projection to the
Dolphin loop. Receipt/effect journals retain their fsync and exactly-once
protocol; persistent writes still require the full executable proof.

New checkpoints follow early White capsule/Boost controls, Movement/Breathing,
HUD publication and effect ACK settlement. Each services durable outgoing
checks, allows socket ACKs and receipts to run, and rechecks room/runtime
identity before resuming. A disconnected/replaced runtime cannot resume
the old generator. `sync_performance` in diagnostics reports cycle duration,
the longest synchronous phase and phase count; 20 ms is a target, not a
claim that every full native scan fits in a frame.
Incoming AP packets wake the synchronization wait immediately. Waiting for
an emulator or slot uses a 250 ms cadence instead of a hot active-emulator
loop; boot detection no longer has the previous one-second idle wait.

For ephemeral native control mailboxes only, a synchronous scope can reuse
the complete PAL executable proof for up to 50 ms after that proof completed.
Every write still performs fresh boot/native-signature reads, module-specific
exact hook checks, live scene/save attribution, compare-before-write and
readback. Persistent progression, physical stats, consumable effects and
legacy non-native images do not use the shared proof. Expiry, boot/signature
change, verification failure, scope exit and exceptions invalidate reuse.
No proof survives an async checkpoint. This deliberately bounds the interval
between whole-DOL scans; it is not an assertion that mutable executable bytes
are cryptographically frozen during that interval.

HUD discovery batches dictionary, group-array, font-record and mailbox reads.
The same pointer bounds, class, signature, unique-owner and name checks remain.
HUD generations continue to require all cast ACKs; only changed host-owned
payloads are republished. Alpha/layout/names and native resource allocation
are unchanged. Pure CSB canonicalization is cached by the entire freshly read
byte string (four entries), never by a heap pointer or a stale scene identity.

Read-only live measurements in the same PAL global-map scene:

| Operation | Previous | Updated |
| --- | --- | --- |
| HUD discovery | 1,644 reads / 7.47 ms | 646 reads / 3.13 ms |
| Three consecutive native-control executable proofs | 1,641 reads / 267.02 ms | 553 reads / 78.23 ms |

Both HUD readers resolved the same live layer, `0x90B52F60`. These are bounded
component benchmarks, not end-to-end AP delivery measurements. No new native
payload or ISO is introduced. Real server receipt-to-effect latency, the
first White capsule at a fast Act start, scene transitions and reconnects
still require a playthrough with the updated client. Existing native queues
retain pickups while the host is busy; this change does not replace their
deduplication or manufacture checks from actor disappearance.

Validation: the full working-tree suite ran 18,509 cases (18,465 passed,
44 failed on the first pass). Fourteen failures caused by decorated-function
code-ID inspection were fixed and all relevant network/package tests then
passed (171 cases). Re-running the original 44 failing nodes against the
pre-change client code reproduced the remaining 30 failures, with 14 passing.
Those failures concern legacy Gecko budget/static payload expectations,
retired schemas/goals/ring totals and the existing option migration; this
performance change does not claim they are fixed. Detailed full-run and
baseline logs are local under `build/sonic_next_pass/reliability_*.txt`.
New focused regressions cover proof expiry/reset/failure, legacy isolation,
HUD bulk owner resolution and corruption rejection, and row-local publication.
The final targeted network/memory/HUD/music/package run passed 319 tests;
two additional async wakeup tests passed. No new native payload was required.
