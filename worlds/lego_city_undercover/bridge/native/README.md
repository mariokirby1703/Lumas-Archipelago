# Experimental native death bridge

Source only: no compiler was found locally. This DLL has not been built, loaded or
tested. It is not included in the read-only diagnostic build. No game memory has
been changed by this implementation work.

Build with MSVC x64 and CMake:

```
cmake -S worlds/lego_city_undercover/bridge/native -B build/lego_city_undercover/native -A x64
cmake --build build/lego_city_undercover/native --config Release
```

The exported `BridgeHook` is a WH_GETMESSAGE callback intended for the game's own
window thread. A controller must verify the exact executable hash, identify its
window thread, create `Local\LCUDeathBridge_<pid>`, and install the hook using the
built DLL. It must not call the native Kill routine in a remote worker thread.
The 32-byte shared command layout is defined in death_bridge.cpp. The only opcode
is 1 (one native player Kill request). Atomic state transition 1 -> 2 prevents
repeated execution. States 3/4 mean returned/rejected, not confirmed death/respawn.

The callback checks PID/thread, a native function prefix, the active player type,
player affiliation, Default context and nonzero health. The prefix check is not a
substitute for full executable hash validation by the controller. Default alone
does not prove that menus/cutscenes are absent, so a first test also requires the
user to report standing in normal free gameplay. Calls can have side effects
before an exception; SEH does not make an unverified native call safe or reversible.

Before live use: compile with warnings enabled, inspect the export/architecture,
test hook installation and teardown with no command, then validate a single Kill
request against the context/health watcher and user-observed respawn. Incoming AP
DeathLink and echo suppression remain unimplemented.
