# Location identity requirements

Explicit user requirement: city locations represent individual completed activities,
such as activating a disguise booth, destroying an ATM, or returning a pig.
Use the specific persistent CityObjective flag/instance identity where verified.
Gold Brick totals and thresholds must not generate locations or additional checks.

A booth completion, its character-token discovery and its Gold Brick reward can
occur together. Do not create multiple checks for the same physical source merely
because several reward fields change. Separate physical character pickups remain
subject to the character randomization requirements.

Gold Brick counts may be recorded as diagnostic corroboration only. A Gold Brick
reward with no mapped activity flag must remain an unresolved source until its
actual completion condition and persistent identity are established. Do not infer
that every Gold Brick source belongs to the currently decoded CityObjective list.
This policy does not prohibit separately verified mission or collectible locations;
their identity must be the actual source, never a cumulative Gold Brick count.
