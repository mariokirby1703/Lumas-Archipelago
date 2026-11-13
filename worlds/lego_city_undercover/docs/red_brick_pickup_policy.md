# Red Brick check timing

Explicit user requirement: send the AP source check when the Red Brick is picked
up, not when the native level-completion screen commits collectibles or reveals
the bonus name. The prison pickup r_pup, source index 185 in prison_maincells.giz,
was observed before and after acquisition while the level was still active.

Detect its transient pickup state or intercept the native collection event once
that path is verified. Bind identity to the mission/source, not displayed bonus
name or current position alone. Journal the source check durably for server retry;
leaving/reloading the level must not duplicate it. Native bonus grants must be
separated from randomized AP rewards. Receiving an AP Red Brick must not itself
generate a pickup check. No transient Red Brick reader or grant suppression is
implemented by this research yet.

After completing the prison mission, the user identified this red brick's bonus
as Studs x2. The completion log shows campaign progression to Act 1 mission 9,
but no dedicated red-brick acquisition event. Preserve the immediate-pickup AP
requirement: the results-screen identification is research evidence, not the
desired future detection time. The separate 2x_Brick_Multi ability name is not
a verified Studs x2 identifier.
