# JobDataMap resource format

Confirmed by a strict parse and byte-exact round-trip of GAME7.DAT's `jobs/lcu.jobdatamap`.
Resource SHA-256: `3fb5c91fd7d0d4ecfaf6c5b1ca3de05f56a6d3810e5dbede93cf822d58b38898`.
This is a table of resource defaults, not a saved-game file. No save has been serialized or modified.

The prefix contains `JobE`, `0.1`, `JobDataMap`, a two-byte version marker, `hEnd`, `<<<<`,
and `JobDataBlock`, with the exact terminators validated by tools/job_data.py.
Next are a zero 32-bit reserved value and a little-endian 32-bit body length.
The body starts with a 16-bit job count. Each job has a NUL-terminated ASCII name and a 16-bit field count.
Each field contains NUL-terminated name and type, a one-byte marker, and a typed default.
The supplied file has Bool defaults encoded as one byte and signed Int defaults as four little-endian bytes.
The final marker is `>>>>` plus NUL; all bytes and declared boundaries are accounted for.

Parsed: 662 jobs, 1,577 fields (679 Bool and 898 Int). Markers are 0 for 768 fields and 1 for 809.
The marker plausibly relates to serialization, but that interpretation is not established by a defaults table alone.
For example, bCompleted is marker 1, yet some nTile fields are also marker 1. Do not call it a save offset or flag.

There are 289 fields whose names contain completion/finish terms, across city, standalone, story and saved-state jobs.
This is a search result count, not a count of independent collectible checks.
Example: `City_Setup.Bonus_Missions.Parkour_TimeTrials.SF_Residential.Start_0922` declares
bCompleted=false, nTile=922, and bDiscovered=false, all marker 1.
Flow_Setup declares Flow_Act=1; Flow_Setup.Act_1 declares Act1_Mission=1 and Act1_Stage=1.
Standalones.MoonBase declares Finished=0 and CutsceneStage=0, but the final-goal interpretation is unverified.

The parser rejects unknown types/markers, duplicate names, invalid Booleans, truncation and size mismatches.
The encoder is used solely to verify understanding in memory; it never overwrites the resource or a save.
Full parsed fields and byte offsets remain under ignored notes/analysis/job_data.json.
