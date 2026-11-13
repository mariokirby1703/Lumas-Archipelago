# Prison directors office observations

User log saved under ignored notes/analysis/user_monitor_prison_directors_office_record.json.
The user reports arrival in the office, use of the stethoscope, lower-left shield
quarter and a skin collected, and a vinyl record currently held.

- Scene component/actor changes occur around 03:10:21–22; manual office note at
  03:10:46. The campaign cursor remains Act 1 mission 8 stage 4, and the job value
  Standalones.Prison.WardensOffice remains zero. Neither is an office-entry detector.
- PRISON_WARD_BL01 (hash 2412184095, bit 757) changes false to true at 03:11:43;
  user marks lower-left quarter at 03:11:53. This is a strong observed association,
  not an independently decoded shield-quarter reward bit.
- PRISON_WARD_CT02_CLUE01 (hash 2139157532, bit 769) changes at 03:13:24. No character
  found/owned/pending event is logged. Do not assert the skin model identity or
  treat this prerequisite clue as a proven token pickup flag.
- #cg_111_SAFE_HIGH_SW selection result changes from 1 to 3 when actor switches
  from COP to Robber around 03:13:34. Native result is not identical to the class
  unlock marker prediction: the class was already unlocked with either outfit.
- At 03:13:47.202 igizitem is added to the actor's attached definitions. Live
  read confirms it remains attached. The user identifies this as the vinyl record;
  the native name alone is generic and does not independently identify a record
  or prove the hand state. Preserve this association without globally relabeling
  every igizitem as a vinyl record.
- Nonempty native marker at (2.582169,0.015240,-0.081030), instance hash 2830876284,
  is removed by 03:13:21. Definition string lookup resolves DetectiveMode and
  SC_DetScan; v11's 0x10001 was a misread string header, corrected in v12.

No game memory writes or native function invocations were performed.

## Mission completion follow-up

user_monitor_prison_mission_complete.json advances the campaign cursor from Act 1
mission 8 to mission 9 stage 1 at 03:30:24. No new red-brick or character acquisition
event appears in the additional 45 log records. The user confirms the results:
the prison red brick is Studs x2 and the collected skin is Häftling (prisoner).
A subsequent read-only live snapshot independently finds Robber_Prisoner model
409 with found_bit=true, owned_byte=0, pending_grant=false, and 12 gold bricks
(previously 11). This establishes found versus purchased separately; it does not
prove which prerequisite clue changed at the exact token pickup moment.
Do not interpret the ability named 2x_Brick_Multi as the Studs x2 red brick based
on its name; that association has not been established. The user's bonus-name
confirmation identifies the prison source, without implementing transient pickup
detection or changing the requirement to send AP checks immediately on pickup.
