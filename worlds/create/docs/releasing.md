# Building a Create release

Run these commands from the repository root with its Python environment activated.
Use the version in `worlds/create/archipelago.json` for the release title and update
`worlds/create/CHANGELOG.md` before building.

## Automated checks

In PowerShell:

```powershell
$env:AP_TEST_WORLDS = "create"
python -m pytest worlds/create/test test/general -q
python Launcher.py "Build APWorlds" -- Create --skip_open_folder
```

The standard Archipelago builder writes `build/apworlds/create.apworld`. It applies
`data/GLOBAL.apignore` and `worlds/create/.apignore`, excluding tests, local notes, and caches.
The archive must contain `create/archipelago.json`, the Python modules, JSON data, client,
documentation, requirements, and launcher icon.

## Play check

Install the built archive into a separate Archipelago installation with no loose `worlds/create`
folder. Generate a fresh seed and check the following with Dolphin and a fresh Save Slot 3:

- The launcher discovers Create Client and opens a generated `.apcreate` file.
- The client connects to the server and Dolphin, then reports Save Slot 3 connected.
- Starting world access and starting objects apply correctly.
- Challenge Sparks and Create Chains send checks once; received objects become usable.
- Disconnecting and reconnecting restores received items.
- Goal World Unlock and a positive Spark Hunt requirement both report completion.

Automated memory tests use a simulated Dolphin interface and do not replace this play check.

## Release files

Attach `create.apworld` and its SHA-256 checksum to the release, and use the changelog entry
as the release notes. Generate the checksum in PowerShell:

```powershell
Get-FileHash build/apworlds/create.apworld -Algorithm SHA256
```

Publish only after the packaged installation and play check pass. Do not reuse generated seeds
across incompatible world versions; generate a new seed with the version players will install.
