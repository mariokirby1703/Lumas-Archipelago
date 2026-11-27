# Isolated debugger lifecycle regression

The first heartbeat test did not exit within its timeout after detach while stopped. Its debugger log showed the breakpoint was hit and removed and detach acknowledged. The text command `quit` was also rejected by x64dbg; it must not be used as evidence of debugger closure.

The corrected sequence removes the breakpoint, resumes, confirms running, detaches and closes only the dedicated test debugger through the automation termination API. The game probe's cleanup now includes resume-before-detach but its public entry point remains disabled pending game-specific investigation.

Actual isolated test: test executable PID 29100; dedicated debugger PID 25704. Breakpoint hit=true, detached=true, heartbeat after detach=true, heartbeat after debugger close=true, child exit=0; test command exit=0. The game and original debugger were not attached or closed in this test. This is not a determination of the user's game crash cause or proof of native menu safety.

Sources: `tools/debugger_lifecycle_target.c`, `tools/test_debugger_lifecycle.py`. Result: `build/lego_city_undercover/debugger/lifecycle_result.json`. Compile using the repository Python's `-m ziglang cc` and run the Python test using the separate debugger venv with a new, empty debugger instance supplied through `--debugger-pid`.

Subsequent passive game attachment/detachment was followed by the user's input
confirmation. A later probe encountered debugger-generated, single-shot TLS
callback breakpoints; cleanup now removes only those generated breakpoints and
our own observation breakpoints before resuming and detaching. The next reported
unresponsive menu recovered after the user switched focus out and back. This
does not resolve the earlier crash report. Live probes remain disabled by the
lockout file. The actual pause-list implementation was found through local EXE
analysis and bounded live reads; installation uses the native bridge without a
debugger.
