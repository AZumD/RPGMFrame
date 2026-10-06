# RPGMFrame

Experimental Linux ARM64 runtime-conversion toolkit for RPG Maker games, initially targeting the Steam Frame.

RPGMFrame is intentionally separate from [RenFrame](https://github.com/AZumD/RenFrame) while the RPG Maker runtime model is still being explored. If both projects stabilize around the same abstractions, they can later become backends of a shared converter.

## Current status

RPGMFrame can:

- detect RPG Maker MV and MZ game directories
- report engine, confidence, evidence, title, payload root, and RPG Maker version
- auto-descend through a single extracted archive wrapper directory
- build **RPG Maker MV** games around a user-supplied Linux ARM64 NW.js runtime
- validate that the supplied NW.js `nw` binary is actually AArch64
- repair an empty NW.js package name while preserving game-specific package settings
- generate a launcher that discovers a running FrameTop Plasma/Xwayland environment

The MV runtime-swap path has been validated on Steam Frame hardware with an RPG Maker MV 1.6.1 game.

MZ is detectable but its build path is intentionally gated until the same transplant has been validated on real hardware.

Later targets:

- automatic NW.js download, checksum verification, and caching
- MZ build support after hardware validation
- RPG Maker XP/VX/VX Ace through mkxp-z
- RPG Maker 2000/2003 through EasyRPG Player

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Inspect

```bash
rpgmframe inspect /path/to/game
rpgmframe inspect /path/to/game --json
```

## Build MV

Pass an extracted Linux ARM64 NW.js runtime:

```bash
rpgmframe build /path/to/mv-game \
  --runtime /path/to/nwjs-v0.117.0-linux-arm64
```

The default output is `<source>-frame/`. Use `-o` to choose another directory and `--force` to replace an existing output.

Launch the built game on the Frame with:

```bash
./launch.sh
```

The launcher preserves a normal desktop environment, but if it detects FrameTop's nested Plasma session it imports that session's display, Xauthority, and runtime variables before starting NW.js.
