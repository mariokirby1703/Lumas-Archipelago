# Experimental Object popup: Dolphin instruction-cache helper

## Object-panel correction (runtime protocol 2)

Install the new `create.apworld` and **replace the existing Gecko helper's
code** with the accompanying `CREATE-AP-Popup-Cache.txt`. The helper now covers
six hook sites. Close the client, stop the game completely, then start CREATE
fresh (do not load an emulator save state) and launch the updated client from
the AP Launcher. The previous code cave is deliberately not overwritten by a
different runtime revision. Your existing AP seed and in-game Slot 3 save can
be reused; the APWorld release version remains unchanged.

The old build successfully created a popup, but selected the Chain award view
and rejected the object because its AP-owned Spark threshold is zero. This
build calls the asset's object panel directly and uses ordinary ownership
instead of the newly-awarded-Spark predicate for the requested object only.

Live checks: `/createpopup 13` should show Automatic Rocket's vanilla image/name
without a Chain/Spark award banner; confirmation should close the panel and
restore input. Then test `/createpopup 6`, newly received Objects, and an ordinary
vanilla Chain completion. `/createpopupstatus` should report `version=2` in the
mailbox. Automated checks verify the patch and fallbacks; the visual result and
controller cleanup still need confirmation in Dolphin.

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
`0x80006040..0x800063E0` and the six hook lines `0x8000DB40`, `0x80092180`,
`0x80092400`, `0x800921E0`, `0x80092420`, `0x80091DA0`, followed by instruction
synchronization. This refreshes both
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

## Verified native/UI path and AP-only interception

The supported executable's symbols identify `0x80074930` as
`FeMessageFlow::BeginChainMsg`, `0x80091C40` as `MakeCreativeChainMessage`, and
`0x800920F0` as `FeSimpleMessage::UpdateUnlocks`. Contrary to the original
briefing's generic-popup assumption, type 4 selects the award view of
`CreativeChainMsg.gfx`. `MakeFePuzzleMessage` at `0x80091620` loads the separate
puzzle/challenge-unlock UI; it is not the Object Unlocked panel.

Inspection of `CreativeChainMsg.gfx` establishes that `AddUnlockImages` stores
the vanilla image/name array and calls `Unlock`. `Display` opens the award
banner. `ShowUnlock(false)` instead loads the object's thumbnail and localized
label into the unlock panel and starts its slide-on animation. The normal
`Event_UnlockFinished -> PlayOutro -> Event_OnOutroEnd` callback path remains.
The award box starts hidden and this patch never calls its `Display` for AP.

The AP-specific interceptions are:

- `0x80091DBC`: replace the factory's final GFx `Display` invocation with
  `_root.ShowUnlock`, using the same movie view and native lifecycle.
- `0x800921E0`: call `IsThingUnlocked` (`0x80025420`) for the exact requested
  zero-threshold AP record. The original `IsThingUnlockedForThisAwardOfSparks`
  (`0x80025560`) rejects zero thresholds and requires a new Spark crossing in
  the current world, which explains the missing object image in the old build.
- `0x80092424`: submit the actual object count (zero or one) and bypass all
  other unlock categories, even when the requested object cannot be displayed.

Both original scan hooks and the new interceptions require ACTIVE status **and
the AP owner's callback context**. A vanilla popup keeps its original scan,
Spark predicate and Display arguments even while an AP popup exists. No global
availability function, UI asset, Spark count, or reward state machine is changed.

The extra routines remain below the mailbox at `0x80006400`; the immutable
`_root.ShowUnlock` string ends within the reserved cave at `0x8000645C`.
No extracted game executable, asset, or third-party RE dependency is packaged.
