# Client and water-entry reliability, 2026-10-16

- A previously bound slot/profile accepts monotonic improvements to intro rank,
  score and best time, including when the result transition was missed. Clear
  rollback, profile/slot changes and unexplained record regressions still fail
  closed. These fields are continuity evidence, not a unique native save UUID;
  an identical copied profile cannot be distinguished cryptographically.
- Opening the GUI Launcher component with no patch/connection now selects a
  player patch and uses the existing ISO/Dolphin installation flow. Cancel
  stops cleanly. Explicit connection, URL, headless and client-only CLI paths
  retain their behavior.
- White capsule permissions and native boost-use/query/gain controls are
  configured before initial HUD publication. The guarded AP boost ceiling is
  reconciled there too; authenticated AP refill receipts remain supported.
- Movement/oxygen controls also run before HUD publication. The HUD avoids a
  second whole-DOL hash when the poll already verified the executable; exact
  publisher/owner and per-write mailbox checks remain.
- Native oxygen updates detect a reused Water plugin whose elapsed timer was
  reset below a positive AP floor, even without the bubble-reset callback.
  This covers zero/5/10/20-second air without waiting for host polling.
  Existing 30/40/60-second timer arithmetic and actor/profile guards remain.

Validation: 233 focused tests passed (binding, launcher selection, native oxygen,
gameplay controls, water fallback, HUD assets/publication, prologue, checkpoints,
official seed patch). A broader runtime selection exposed an existing mismatch
between the locally edited DeathLink anti-echo implementation and the old
expiration test; that unrelated test was not changed to hide the failure.

New APWorld/client and a rebuilt ISO are required for native oxygen and resource
changes. No new seed is required. Prior known component hashes remain accepted
for rebuilding from the user's original ISO. No save or running journal was
edited. The active client still has its old imported code until restarted.

Pending live verification: cold-start sprint into White capsules with White
absent, enemy/script boost grants and AP-only refill preservation, HUD initial
publication latency, repeated water entries and bubbles at every breathing
level, and record improvement across reconnect. Earlier host configuration
reduces the startup window; it does not prove a first-frame lock before the
first authenticated client snapshot. Do not report these as live verified.
