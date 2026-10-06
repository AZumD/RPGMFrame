# RPGMFrame

Experimental Linux ARM64 runtime-conversion toolkit for RPG Maker games, initially targeting the Steam Frame.

RPGMFrame is intentionally separate from [RenFrame](https://github.com/AZumD/RenFrame) while the RPG Maker runtime model is still being explored. If both projects stabilize around the same abstractions, they can later become backends of a shared converter.

## Current status

RPGMFrame can:

- detect RPG Maker MV and MZ game directories
- report engine, confidence, evidence, title, payload root, and RPG Maker version
- auto-descend through unambiguous chains of extracted archive wrapper directories
- build **RPG Maker MV** games around Linux ARM64 NW.js
- build **RPG Maker MZ** games around Linux ARM64 NW.js
- build directly from `.zip` downloads without manual extraction
- optionally package completed builds as portable `.tar.gz` archives
- automatically download, SHA256-verify, and cache the pinned NW.js ARM64 runtime
- accept a manually supplied NW.js runtime as an override
- validate that the NW.js `nw` binary is actually AArch64
- repair an empty NW.js package name while preserving game-specific package settings
- generate a launcher that discovers a running FrameTop Plasma/Xwayland environment
- provide Windows-style environment defaults such as LOCALAPPDATA, APPDATA, and USERPROFILE
- preserve game-owned package-root companion files while dropping the old Windows NW.js runtime
- inject a generic case-insensitive Linux path compatibility shim for browser assets and Node fs reads
- repair a missing MV fpsmeter.js include when the core requires it and the shipped library is present

The MV runtime-swap path has been validated on Steam Frame hardware with an RPG Maker MV 1.6.1 game.

Both MV and MZ runtime-swap paths have now been validated on Steam Frame hardware. MV was validated with Jailbreak (RPG Maker MV 1.6.1) and with OMORI 1.0.8d (RPG Maker MV 1.6.1), using a clean RPGMFrame build with no hand-edits to the converted output. MZ was validated with Look Outside 0.30 (RPG Maker MZ 1.8.1), including gameplay, controller input, audio, menus/settings, save/load, and relaunch.

OMORI is intentionally treated as a compatibility stress test rather than a game-specific target. The fixes learned from it are implemented as generic Windows/NW.js-to-Linux behavior. See [Compatibility notes](docs/compatibility.md).

The default runtime is pinned to **NW.js 0.117.0**, the version currently validated on Steam Frame. Use `--runtime-version` to test another official release or `--runtime` to supply an extracted runtime directly.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Inspect

```bash
rpgmframe inspect /path/to/game
rpgmframe inspect /path/to/game --json
```

## Build MV / MZ

Normal use now needs only the game directory:

```bash
rpgmframe build /path/to/mv-game
```

ZIP downloads can be passed directly:

```bash
rpgmframe build /path/to/game.zip
```

RPGMFrame safely extracts ZIP input into a temporary workspace, builds from it, and removes the temporary files afterwards.

To also create a transfer-ready archive:

```bash
rpgmframe build /path/to/game.zip --archive
```

With the default output naming, that produces both:

```text
game-frame/
game-linux-aarch64.tar.gz
```

On the first build, RPGMFrame downloads the official Linux ARM64 NW.js tarball and `SHASUMS256.txt`, verifies the archive, and caches the extracted runtime under `~/.cache/rpgmframe/runtimes/nwjs/`. Later builds reuse that cache.

Override the pinned runtime version:

```bash
rpgmframe build /path/to/mv-game --runtime-version 0.117.0
```

Or supply an already extracted runtime:

```bash
rpgmframe build /path/to/mv-game \
  --runtime /path/to/nwjs-v0.117.0-linux-arm64
```

The default output is `<source>-frame/` (with `.zip` removed for archive input). Use `-o` to choose another directory and `--force` to replace an existing output or packaged archive.

Launch the built game on the Frame with:

```bash
./launch.sh
```

The launcher preserves a normal desktop environment, but if it detects FrameTop's nested Plasma session it imports that session's display, Xauthority, and runtime variables before starting NW.js. It also maps common Windows profile environment variables to Linux/XDG locations and starts NW.js with the converted package as its working directory.

Converted MV/MZ payloads include a small RPGMFrame compatibility shim. It only rewrites failed, package-local reads when the requested path differs from an existing file by case. This covers both browser-side resources such as images/audio and Node fs calls used by plugins. Exact paths are left alone, external paths are not rewritten, and case-colliding source trees are reported instead of guessed.
