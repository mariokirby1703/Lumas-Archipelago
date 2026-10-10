# Enabled Egg Medal code skipped by Dolphin

The user enabled all four groups and restarted emulation, but Game Land 1-1's
Medal check did not fire. Both the actual Dolphin INI and enabled list contained
the fourth group. Read-only live observation found original `mr r3,r28` at
`0x802F27C4`, and the running GCT ended at `0x80002FE0`, immediately after the
gameplay controls. No Medal C2 header/payload was present. The medal actor was
correctly identified as Game Land 1-1, object 57. No guest writes were made.

Dolphin's [Gecko installer](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/GeckoCode.cpp)
skips a whole active group if it cannot fit before the code-table boundary.
The installed `Sys/codehandler.bin` is 2880 bytes. From its standard installer
base `0x80001800` to end `0x80003000`, subtracting the handler and GCT terminator
leaves **3256 bytes** for codes. The previous four-group export exceeded this.
Restarting or checking the box cannot make an oversized group fit.

The compact export uses **3216 bytes**, leaving 40 bytes of headroom with this
handler. It omits the inert historical coloured-Wisp query hook. Production
still recognizes and neutralizes that exact older hook when present. The six
active gameplay hooks share their disc/revision conditional scope, retain each
original-instruction check and reset once at the end of the group. White Boost
use/query/refill, three Game Land speed gates, capsule lifecycle, progression
and Medal capture payloads retain their behavior. On the first handler pass
all original instructions match; on later passes installed branches prevent
reinstallation and preserve mutable AP control data.

119 targeted offline tests passed, including full export size, guarded first-pass
installation of every active hook, subsequent-pass suppression, wrong-disc
rejection, native gameplay/capsule PPC and package checks. The table simulation
is not the actual Dolphin interpreter. Live installation of the compact four
groups and a Medal acknowledgement are still required. Enable all four updated
groups and fully restart emulation, then verify `available: true, armed: true`
before collecting the Game Land 1-1 medal.

The exporter does not enlarge or relocate Dolphin's table or inject executable
bytes through DME. More hooks need additional space reductions or a separately
verified installation strategy; 40 bytes is not a general expansion budget.

## Live validation after the compact export

After updating all four codes and restarting, read-only Dolphin inspection in
Game Land 1-1 (`stgD10`) verified the Medal thunk installed and armed for the
catalogued object 57. Its native latch was zero before collection. All six
required Boost/speed hooks were installed; the intentionally omitted inert
`boost` query hook was absent. The user then collected the medal and supplied:

```text
Pickup detected: Egg Medals ['Game Land 1-1 - Egg Medal']; Location queued: [847005000]
LocationChecks sent: [847005000]
Location acknowledged: [847005000]
```

This validates the compact installation, native pickup capture and real AP
transport/acknowledgement for Game Land 1-1. Other Medal locations, pickup before
host arming, and death/reconnect persistence for this check remain separate tests.

The user subsequently confirmed that reconnecting the client and replaying
Game Land 1-1 passed the requested duplicate/completion check. They also tested
Game Land 2-1's Egg Medal and reported it worked. These are user-confirmed
results; no additional 2-1 log lines or independent RAM capture were supplied.
Death persistence, the remaining 19 Medal locations and pickups before host
arming are still unverified by this session.
