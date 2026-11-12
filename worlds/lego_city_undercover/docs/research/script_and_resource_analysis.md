# Script and resource evidence

The expanded reproducible extraction covers 1,779 files and 10,768,902 bytes.
It includes the archived jobs, character project metadata and all 957 .giz resources, while leaving original archives intact.
This does not mean every proprietary format or gameplay mechanic is understood.

## Scripts

tools/script_catalogue.py lexically indexes 745 scripts without executing them. Comments and quoted text are excluded
from call recognition. Legacy Windows-1252 files are decoded explicitly; the encoding is recorded per source.
The catalogue contains 2,654 selected calls, including:

| Action | Calls |
|---|---:|
| CityObjective_IsComplete | 50 |
| CityObjective_SetComplete | 31 |
| UnlockAbility | 122 |
| LockAbility | 2 |
| IsAbilityUnlocked | 10 |
| GetValue / SetValue | 900 / 1,306 |
| CommitCollectables / TriggerAutoSave | 20 / 61 |
| Achievements_MarkChapterStart / Complete | 15 / 10 |

There are 145 possible objective-name arguments to completion calls, of which 143 match scanner instance names.
A direct string argument is distinguished from possible file-local variable assignments.
This is an over-approximation: assignments in different branches are not proven to reach a particular call.
The reports preserve source path, line number and file hash. Archived/debug scripts remain explicitly identifiable by path.
Chapter calls alone do not establish 15 persistent chapter-completion flags: one chapter can have multiple calls,
and other completions may happen in engine code or resource events.

The two LockAbility calls found here both target superbuild in vehicle-drop setup. They are static evidence that
normal gameplay can remove an unlock; repeated blanket external writes would conflict with script behavior.
The end-of-story multiplier script calls UnlockAbility(2x_Brick_Multi), CommitCollectables(ABILITIES), and TriggerAutoSave.
This shows that requesting an ability and committing its collectible/save state are distinct operations.

## GIZ resources

tools/resource_catalogue.py bounds-checks section headers in 947 resources with the observed v17/zero prefix.
Ten other headers are reported as unsupported, including a nested CC4 resource; they are not force-parsed.
Section payloads and final name tables remain opaque. This parser does not infer object positions or pickup persistence.
There are 304 GizmoPickup sections and 66 GizSuperBuild sections across these resources.
Those numbers count sections, not individual pickups or Super Builds. Builder/test/title resources are included.
Only two scanner names occur as literal substrings in these resources; literal occurrences are not runtime activation evidence.

Large catalogues and original data remain ignored under notes/analysis and notes/extracted.
