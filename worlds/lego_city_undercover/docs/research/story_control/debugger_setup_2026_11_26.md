# Native debugger setup and first attachment

## User-reported crash — live probes disabled

The user subsequently reported that closing the debugger crashes the game. Earlier `detached=true` responses are API acknowledgements only and must **not** be interpreted as proof of safe game continuation. The common CLI entry point now refuses live attachment until debugger lifetime and breakpoint cleanup have been validated on an isolated process. No additional game attachment is authorized by the previous successful API results.

At the report, the observation target was PID 36908; a different game process, PID 5708, was running. This does not establish the crash cause. The debugger application itself had not been closed by the probe; its API disconnect and game detach are separate operations. The cause remains unresolved. No further debugger close or game mutation was performed in response.

Installed locally under `build/lego_city_undercover/debugger/`:

- Official portable x64dbg snapshot 2026.05.27, SHA-256 checked against the GitHub release asset digest.
- x64dbg Automate plugin 0.8.1, likewise hash checked; Python client 0.9.2 (`ghost_fungus` protocol).
- Separate Python venv; project dependencies unchanged. No global debugger association or system installation.

Reproduce with `tools/setup_pause_debugger.ps1`. The debugger is not part of the public APWorld. Launch x64dbg normally or through `Start-Process -WindowStyle Hidden -PassThru`; the latter was used for the automated session. The Python API handshake succeeded (debugger version 25).

`tools/pause_debugger_probe.py --debugger-pid <pid> --seconds 8` runs with the separate debugger Python. It verifies the running and local executable identity, compares original entry bytes, briefly attaches, selects an existing CPU-active thread, installs single-shot observation breakpoints and removes its breakpoints/detaches in finally. It never resumes game-suspended helper threads. No register/engine/save/asset writes are used. Software breakpoint insertion temporarily changes code bytes.

Actual test: process 14352, supported DX11 hash, module base 0x7ff7292c0000. Final probe exited 0 and reported detached=true. Candidates 0x797d0, 0x7a270, 0x1f9830 and 0x556770 produced **zero hits** in eight seconds. This does not establish the correct pause-menu path or callback contract. Earlier attach attempts selected a suspended helper thread; they were detached successfully and the probe was corrected to select an active existing thread before pausing.

Windows Computer Use failed repeatedly, including after kernel reset, with `Computer Use native pipe is unavailable ... os error 2`. No substitute input injection was used. Consequently no automated menu open/close/input cycle was performed. Debugger command/memory automation is working independently of that unavailable UI service.

Evidence: `build/lego_city_undercover/debugger/menu_probe.json`, `debugger_log.txt`, `session_pid.txt`. The game was left detached; the debugger application remains running. No new chapter menu or chapter activation was implemented by this setup.

References: [official x64dbg release](https://github.com/x64dbg/x64dbg/releases/tag/2026.05.27), [automation plugin installation](https://dariushoule.github.io/x64dbg-automate-pyclient/installation/).
