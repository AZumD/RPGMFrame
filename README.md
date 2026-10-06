# RPGMFrame

Experimental Linux ARM64 runtime-conversion toolkit for RPG Maker games, initially targeting the Steam Frame.

RPGMFrame is intentionally separate from [RenFrame](https://github.com/AZumD/RenFrame) while the RPG Maker runtime model is still being explored. If both projects stabilize around the same abstractions, they can later become backends of a shared converter.

## First target: RPG Maker MV / MZ

The first milestone is deliberately small:

- detect RPG Maker MV and MZ game directories
- report the detected engine, confidence, evidence, and RPG Maker version when available
- expose detection through `rpgmframe inspect`
- keep runtime download and conversion out of the detector

Later milestones can add:

- Linux ARM64 NW.js runtime resolution and caching
- MV/MZ build output and launchers
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

Inspect a game:

```bash
rpgmframe inspect /path/to/game
rpgmframe inspect /path/to/game --json
```

## Status

Very early prototype. No conversion is performed yet.
