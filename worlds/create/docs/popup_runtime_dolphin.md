# Experimental Object popup: Dolphin instruction-cache helper

The external client can write and verify PPC instructions in RAM, but
`dolphin_memory_engine` cannot invalidate Dolphin's emulated instruction cache.
This also affects the ordinary Interpreter: it fetches instructions through
`MMU::TryReadInstruction`, which reads `ppc_state.iCache`. Switching CPU engines
alone therefore does not establish that the new instructions are executed.

## Install the helper for the test branch

1. Close the Create Client and stop CREATE in Dolphin.
2. In Dolphin's configuration, enable **Enable Cheats**. You can use the normal
   **JIT Recompiler** again; Interpreter mode is not required by this helper.
3. Right-click CREATE in Dolphin's game list, choose **Properties**, then
   **Gecko Codes**, and **Add New Code**.
4. Name it **CREATE AP Popup Instruction Cache**. Paste the code from the
   accompanying `CREATE-AP-Popup-Cache.txt` into the code field and save it.
   The client command `/createpopupcache` prints the same code.
5. Check the new code to enable it. Start the game fresh, load Save Slot 3,
   and start the updated Create Client from the AP Launcher.
6. Stay in the Hub/world and look for **runtime hook heartbeat confirmed**.
   If an earlier probe timed out, use `/createpopupretry` in the client.
7. Test `/createpopup 13`, close normally, then `/createpopup 6`.
   `/createpopupstatus` reports heartbeat, mailbox, modal layer and hook words.

Do not paste the helper into the AR Codes or Patches tab. It is a Gecko C0 code.
No new seed or APWorld version bump is needed. The file is an experimental
client build, not a published release.

## What the helper does

Dolphin's own Gecko handler executes a small, normally returning C0 function
each frame. It issues `icbi` for the code-cave instruction lines
`0x80006040..0x800063E0` and the three hook lines `0x8000DB40`, `0x80092180`,
`0x80092400`, followed by instruction synchronization. This refreshes both
instruction-cache and JIT visibility of the client's changes, including
restored original instructions after uninstall. The handler lives in Dolphin's
Gecko allocation, outside the popup cave.

The helper only writes its temporary stack frame and preserves registers. It
does not install popup hooks, write mailbox data, unlock items, select an object,
construct a popup, force modal state, or invoke the Create Chain reward flow.
Code-cave validation, hook validation, safe request timing, and heartbeat
confirmation remain the client's responsibility. Invalidating these small
regions every frame may add some recompilation overhead in this test build.

Disable this helper when finished testing. Its intended cache effect is based
on Dolphin's implementation; actual heartbeat and popup behavior still require
the live test. If heartbeat stays zero, provide `/createpopupstatus` output;
an unexecuted call site remains another possible cause.

## Source evidence

- [Interpreter instruction fetch](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Interpreter/Interpreter.cpp)
- [MMU::Read_Opcode / TryReadInstruction and iCache](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/MMU.cpp)
- [Dolphin Gecko installation and execution](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/GeckoCode.cpp)
- [Gecko C0 continuation ABI, _execute](https://github.com/dolphin-emu/dolphin/blob/master/docs/codehandler.s)

These explain why a successful RAM readback and `modal=0` do not prove that the
dispatcher has executed. The client must still observe a changing heartbeat.
