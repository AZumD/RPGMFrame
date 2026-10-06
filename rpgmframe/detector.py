"""Conservative RPG Maker MV/MZ directory detection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpgmframe.models import (
    Compatibility,
    Confidence,
    EngineVariant,
    GameInspection,
)

_VERSION_RE = re.compile(
    r"""RPGMAKER_VERSION\s*=\s*["'](?P<version>[^"']+)["']""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Candidate:
    engine: EngineVariant
    source_root: Path
    game_root: Path
    core_file: Path
    score: int
    evidence: tuple[str, ...]


def _normalize_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_text_head(path: Path, limit: int = 131072) -> str | None:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _score_candidate(
    evidence_root: Path,
    source_root: Path,
    *,
    engine: EngineVariant,
    game_root: Path,
    core_name: str,
) -> _Candidate | None:
    core = game_root / "js" / core_name
    if not core.is_file():
        return None

    evidence: list[str] = [_relative(core, evidence_root)]
    score = 6

    system_json = game_root / "data" / "System.json"
    if system_json.is_file():
        score += 3
        evidence.append(_relative(system_json, evidence_root))

    index_html = game_root / "index.html"
    if index_html.is_file():
        score += 1
        evidence.append(_relative(index_html, evidence_root))

    package_candidates = (source_root / "package.json", game_root / "package.json")
    package = next((p for p in package_candidates if p.is_file()), None)
    if package is not None:
        score += 1
        evidence.append(_relative(package, evidence_root))

    return _Candidate(
        engine=engine,
        source_root=source_root,
        game_root=game_root,
        core_file=core,
        score=score,
        evidence=tuple(dict.fromkeys(evidence)),
    )


def _collect_candidates(source_root: Path, *, evidence_root: Path) -> list[_Candidate]:
    candidates: list[_Candidate] = []

    mv_www = _score_candidate(
        evidence_root,
        source_root,
        engine=EngineVariant.MV,
        game_root=source_root / "www",
        core_name="rpg_core.js",
    )
    if mv_www:
        candidates.append(mv_www)

    mv_root = _score_candidate(
        evidence_root,
        source_root,
        engine=EngineVariant.MV,
        game_root=source_root,
        core_name="rpg_core.js",
    )
    if mv_root:
        candidates.append(mv_root)

    mz_root = _score_candidate(
        evidence_root,
        source_root,
        engine=EngineVariant.MZ,
        game_root=source_root,
        core_name="rmmz_core.js",
    )
    if mz_root:
        candidates.append(mz_root)

    mz_www = _score_candidate(
        evidence_root,
        source_root,
        engine=EngineVariant.MZ,
        game_root=source_root / "www",
        core_name="rmmz_core.js",
    )
    if mz_www:
        candidates.append(mz_www)

    return candidates


def _single_wrapper_child(root: Path) -> Path | None:
    """
    Return a single obvious wrapper directory, if present.

    Extracted archives commonly contain one top-level folder around the actual
    game. Hidden metadata directories such as __MACOSX are ignored.
    """
    try:
        children = [
            child
            for child in root.iterdir()
            if child.is_dir()
            and not child.name.startswith(".")
            and child.name != "__MACOSX"
        ]
    except OSError:
        return None

    return children[0] if len(children) == 1 else None


def _find_package_json(source_root: Path, game_root: Path) -> Path | None:
    for candidate in (source_root / "package.json", game_root / "package.json"):
        if candidate.is_file():
            return candidate
    return None


def _detect_game_name(game_root: Path, package_json: Path | None) -> str | None:
    system = _read_json(game_root / "data" / "System.json")
    if system:
        title = system.get("gameTitle")
        if isinstance(title, str) and title.strip():
            return title.strip()

    if package_json:
        package = _read_json(package_json)
        if package:
            window = package.get("window")
            if isinstance(window, dict):
                title = window.get("title")
                if isinstance(title, str) and title.strip():
                    return title.strip()
            name = package.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

    return None


def _detect_engine_version(core_file: Path) -> str | None:
    text = _read_text_head(core_file)
    if not text:
        return None
    match = _VERSION_RE.search(text)
    return match.group("version").strip() if match else None


def _confidence_for_score(score: int) -> Confidence:
    if score >= 9:
        return Confidence.HIGH
    if score >= 7:
        return Confidence.MEDIUM
    return Confidence.LOW


def inspect_game(path: Path | str) -> GameInspection:
    """
    Detect RPG Maker MV/MZ using engine-specific JavaScript runtime files.

    Generic markers such as package.json are never sufficient on their own.
    If the selected directory contains an unambiguous chain of wrapper
    directories, RPGMFrame descends through it automatically. This handles
    archives shaped like release/game/www without guessing across siblings.
    """
    root = _normalize_path(path)

    if not root.exists():
        return GameInspection(
            source_path=root,
            warnings=[f"Path does not exist: {root}"],
        )
    if not root.is_dir():
        return GameInspection(
            source_path=root,
            warnings=[f"Path is not a directory: {root}"],
        )

    current_root = root
    wrapper_chain: list[Path] = []
    seen_roots = {root}
    candidates = _collect_candidates(current_root, evidence_root=root)

    while not candidates and len(wrapper_chain) < 16:
        wrapper = _single_wrapper_child(current_root)
        if wrapper is None:
            break
        resolved_wrapper = wrapper.resolve()
        if resolved_wrapper in seen_roots:
            break
        seen_roots.add(resolved_wrapper)
        wrapper_chain.append(wrapper)
        current_root = wrapper
        candidates = _collect_candidates(current_root, evidence_root=root)

    if not candidates:
        return GameInspection(
            source_path=root,
            warnings=[
                "No RPG Maker MV/MZ engine core was found "
                "(expected rpg_core.js or rmmz_core.js)."
            ],
        )

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    best = candidates[0]

    if len(candidates) > 1:
        runner_up = candidates[1]
        if runner_up.score == best.score and runner_up.engine is not best.engine:
            evidence = list(dict.fromkeys(best.evidence + runner_up.evidence))
            return GameInspection(
                source_path=root,
                evidence=evidence,
                warnings=[
                    "Conflicting MV and MZ engine signatures have equal confidence; "
                    "refusing to guess."
                ],
            )

    package_json = _find_package_json(best.source_root, best.game_root)
    warnings: list[str] = []
    if wrapper_chain:
        warnings.append(
            "Auto-descended through wrapper directories: "
            f"{_relative(wrapper_chain[-1], root)}"
        )
    if not (best.game_root / "data" / "System.json").is_file():
        warnings.append(
            "Engine core found, but data/System.json is missing; "
            "this may be an incomplete game directory."
        )

    return GameInspection(
        source_path=root,
        engine=best.engine,
        runtime="nwjs",
        confidence=_confidence_for_score(best.score),
        game_root=best.game_root,
        game_name=_detect_game_name(best.game_root, package_json) or best.source_root.name,
        engine_version=_detect_engine_version(best.core_file),
        package_json=package_json,
        evidence=list(best.evidence),
        warnings=warnings,
        compatibility=Compatibility.SUPPORTED,
    )
