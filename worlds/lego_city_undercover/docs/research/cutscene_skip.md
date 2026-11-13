# Native N0CUT5 cutscene skip permission

Static evidence in the pinned Steam executable:

- Literal N0CUT5 at file offset 0xd49e00, code reference RVA 0x7eff89.
- Successful comparison at 0x7eff98 passes dl=1 and the object from global
  RVA 0x17ebcf8 to function 0x7b7490, then returns success.
- 0x7b7490 is a setter: byte [rcx+0x190] = dl; no other instructions before ret.
- The script property allowcutskip (reference 0x7ec7d5) uses the same setter,
  passing a parsed boolean. Thus the cheat and native script option converge on
  the same runtime permission, rather than requiring cheat-menu automation.

This is a concrete candidate for an AP quality-of-life option, applied through
the eventual guarded bridge after initialization/reinitialization. Preserve
native skip handling; do not jump story jobs or force mission completion. This
permits skipping rather than proving automatic playback skipping or coverage of
every cinematic. Native scripts may reset the permission and need observation.

Manual code-entry validation on 2026-11-13: before snapshot at 04:28:52 UTC
records byte 0; after the user's confirmed N0CUT5 activation, 04:31:07 UTC records
byte 1. Same PID 25356 and same manager instance; no process writes by the reader.
Snapshots are saved under ignored notes/analysis/cutscene_skip_before_manual_code.json
and cutscene_skip_after_manual_code.json. This confirms the code-to-flag transition
live. Actual cutscene skipping and reset/reinitialization behavior remain to test.
Automatic activation is not implemented. The monitor remains read-only.

Community usage evidence: https://www.speedrun.com/lcu/forums/m2klp documents the
code, blank seventh character and session-limited effect. Static local findings
above independently establish the code/setter relationship in this exact build.
