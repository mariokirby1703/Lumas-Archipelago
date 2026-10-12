# V11: native owned movement machine and Grand Map refresh

Live read-only PAL evidence (2026-10-12):
- New Game TR Act 1: ability controller 80B58A40, adjacent request machine
  80B58A80, native current/request 2/2. This accidental adjacency explains
  earlier successful movement denials.
- Results: a new Sonic actor/controller is created. Gameplay arming is not
  authorized in results, independently of the state-machine identity.
- TR Act 2 (stg130): ability controller 80B4C040, request machine 80B5BC00;
  the owned machine has current/request 2/2. Controller+40 contains 91637EA4,
  not a state-machine vtable. The old subtraction-by-40 guest test cannot
  authenticate this real machine.
- Native 800B033C initializes the ability controller through +34, not an
  embedded state machine. 80032C9C constructs 8075A0F8 and stores its owner
  at +28. The player+70 -> +8 chain and backreference were verified live.

V11 uses this chain for native state reads, host authorization and the guest
request comparison. The guest independently checks the machine vtable and
its exact attributed Sonic owner. Denial preserves the original native
predecessor and compare/callback flow; native state words are never written.
Previously installed V10 is recognized for executable identity only and is
not armed with V11's different mailbox semantics.

The combined V11 profile restores the Grand Map refresh C2 that V10 removed.
It fits 3256 bytes by saving scratch GPRs with multiple-register instructions
and using a compact capsule thunk at the native void update's post-call site.
There are no live volatile FPR/CTR values after the original call to
800D4864 and before the continuation. Nonvolatile GPRs, LR and CR remain
preserved; capsule native factory/state functions and ownership guards are
unchanged. The standard full-save profile remains supported.

Install the complete SNCP8P_movement_request_gate_v11.ini in place of all
older movement/standard groups, plus the rebuilt APWorld, then restart both
client and emulation. Do not hot-patch running PPC through DME.

Offline encoded-instruction tests cover owned/foreign machines, all movement
requests, unknown states and invalid predecessors. The real owned chain was
read in Dolphin, but V11 input locking, compact capsule behavior and restored
World Access still require a live acceptance test after installation.


## First V11 live acceptance sample

2026-10-12, user restarted client/emulation with the complete V11 profile
and entered Tropical Resort Act 2 (native stg130). Full PAL text recovery
passed; exact V11 movement payload recognized (legacy=False), Grand Map
refresh mailbox present, compact capsule payload recognized. Request machine
80B5B040 was armed for Sonic actor 90FC8C80 with mask 0. Native denial count
was 8, last denied request 43 (Crouch). User independently reported that moves
were locked in Act 2. This verifies real native execution in that Act, not
every movement capability or scene transition. Explicit Double Jump/Crouch,
normal movement recovery, another Act/re-entry and actual World Access
refresh acceptance are still pending. Capsule pickup behavior in this compact
profile has not yet been independently reported by the user.


## Intermittent authorization failure found in live V11

User reported briefly successful Mid-Air Boost, delayed Double Jump, Stomp
and Crouch after initial successful locks. Read-only sampling caught the
mailbox changing from the attributed 80B5B040 machine to zero while scene
stg130, Sonic owner and native request machine remained unchanged. Denials
increased from 92 through 101 while armed, then stopped while machine=0;
forbidden native states 9 and 44 subsequently appeared. A later user status
showed it armed again with denial count 346. V11 is therefore NOT yet a
reliable completed movement lock.

Host update: a confirmed same-stage actor/machine is no longer revoked by
transient native state sentinels or temporarily low snapshot stability. A
missing secondary player read in the same verified gameplay stage defers
ALL host writes and retains stage-local observations; it does not reuse an
unverified actor as write authority. Every later actual update resolves the
owned machine again; the guest retains independent machine vtable/owner
checks. Different stages/actors still require fresh arming. Regression tests
cover these cases. Live acceptance of this host update remains pending.
Gecko instructions are unchanged; only the AP client must be updated.


## Live host-update result (code ID 9cb85a208903)

User updated only the client, retained V11 Gecko/emulation, and repeated
Crouch, Double Jump, Mid-Air Boost and Stomp attempts in TR Act 2. In a
140-sample read-only run, the gate pointer never became zero (0/140); native
denials increased 80 -> 188. Observed current states were only -1, 2, 3, 5,
6, 7 and 15, plus secondary-reader misses; no gated action state was observed.
The user independently reported that all tested movements remained blocked.
This validates this specific no-item Act-2 test. Other Acts, item-granted
abilities, and refreshed World Access still require their own live checks.
