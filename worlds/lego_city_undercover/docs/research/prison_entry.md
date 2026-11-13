# Prison entry and monitor preparation

Local enter_prison.sf uses IS_Prison_Island_1525/1526 and 1426, plays
11_Meet_BlueA, sets Flow_Completed.Act_1_EnterPrison and
Flow_Saves.Act_1.Meet_Blue_at_Prison.MeetBluePrison, then campaign cursor
Act1 mission 8 stage 4. Entry completion is not assignment completion.

standalones/prison/prison.sf waits for its Finished value >0. It resets Finished
to zero when transitioning to mission 9/stage 1 or leaving an already-played
assignment. It can force player 1 to Cop at first story entry. Thus Finished is
a transient mission value, not a durable collectible completion bit.

The resource Job table verifies Int fields Finished, WardensOffice, Painting_Opened,
Rex_Enemies, Rex_Conversation, Switch01/02/03 and Rex_Punchbag. Their runtime changes
are now monitor diagnosis events, including resets; they never emit AP checks.
Their individual gameplay semantics still need observed correlation.

Before traveling: connect the new monitor in the city, mark Gefängnis betreten
once controllable, mark shield quarters/Hero milestones and the robber disguise
unlock as they happen. Keep native automatic character/ability event detection on.
No native robber-grant hook, quarter reader or permanent assignment completion
reader has been implemented by this preparation.
