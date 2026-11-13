# AP reward previews in activity popups

User-approved feature idea: replace the vanilla reward description in activity
start/confirmation popups with the actual AP item name and recipient. The observed
Parkour popup is the first research candidate; races and Super Builds may provide
similar opportunities. UI text/icon replacement is not implemented or verified.

Resolve the exact activity's AP location, request server scouting information using
LocationScouts/LocationInfo, and display the item name and receiving player from
the connected session. Never infer the reward from vanilla character/Gold Brick
icons. If scouting data is unavailable, show an honest unknown/loading state.
Previewing must not send a completion check, charge currency, or grant an item.
Invalidate cached previews when seed/player binding changes. Respect any configured
reward-preview/spoiler policy. Replace misleading vanilla reward icons if feasible;
do not imply additional checks for correlated character or Gold Brick rewards.

TODO: identify Parkour popup text bindings, correlate its active mission instance
with an AP location, and test dynamic text replacement via the supported bridge.
