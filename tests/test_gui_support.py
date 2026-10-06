from __future__ import annotations

import json
import zipfile
from pathlib import Path

from rpgmframe.gui_support import (
    inspect_source_summary,
    output_path_for_source,
    source_base_name,
)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mv_tree(root: Path) -> None:
    wrapper = root / "release" / "game"
    _write(
        wrapper / "www/js/rpg_core.js",
        'Utils.RPGMAKER_VERSION = "1.6.1";',
    )
    _write(
        wrapper / "www/data/System.json",
        json.dumps({"gameTitle": "GUI Fixture"}),
    )
    _write(wrapper / "www/index.html", "<html></html>")
    _write(
        wrapper / "package.json",
        json.dumps({"name": "fixture", "main": "www/index.html"}),
    )


def test_source_base_name_drops_zip_suffix() -> None:
    assert source_base_name(Path("/tmp/Fancy Game.zip")) == "Fancy Game"
    assert source_base_name(Path("/tmp/Fancy Game")) == "Fancy Game"


def test_output_path_for_source_uses_selected_output_directory(tmp_path: Path) -> None:
    output = output_path_for_source(
        Path("/elsewhere/Game.zip"),
        tmp_path,
    )
    assert output == tmp_path / "Game-frame"


def test_inspect_source_summary_for_wrapped_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _mv_tree(source)

    summary = inspect_source_summary(source)

    assert summary.recognized
    assert summary.engine == "mv"
    assert summary.engine_version == "1.6.1"
    assert summary.game_name == "GUI Fixture"
    assert summary.compatibility == "supported"


def test_inspect_source_summary_for_zip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _mv_tree(source)
    archive = tmp_path / "fixture.zip"

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in source.rglob("*"):
            if path.is_file():
                zipped.write(path, path.relative_to(source))

    summary = inspect_source_summary(archive)

    assert summary.recognized
    assert summary.engine == "mv"
    assert summary.game_name == "GUI Fixture"
