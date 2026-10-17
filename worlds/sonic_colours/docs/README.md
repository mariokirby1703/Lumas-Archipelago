# Sonic Colours documentation

Start with [setup](setup_en.md), [release patch workflow](release_patch.md),
and the root [TODO](../TODO.md). The current client synchronization design
and measured limits are in [synchronization performance](sync_performance.md).

Current technical references:

- [Native ISO patching](native_patch_migration.md)
- [Native event verification and remaining live tests](native_events_verification.md)
- [Item HUD](ap_hud_connected.md) and [result coordinates](result_hud_coordinates.md)
- [Game Land column refresh](game_land_collapsed_columns.md)
- [Finite-song native loops](finite_music_native_loop.md) and [random pool](music_pool_v2.md)
- [White capsule alternate models](white_capsule_mode2.md)

Dated movement, stabilization and research reports describe historical
implementations and evidence, not current installation instructions. They
remain available because they explain supported legacy hooks and native
addresses. Original game files and local dumps belong to ignored `notes/`;
the release builder excludes those, tests, documentation and Python caches.
The obsolete pre-renderer `ap_hud_ticker_status.md` report was removed;
its history remains in Git.
