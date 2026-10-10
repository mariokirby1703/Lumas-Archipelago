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
