"""Resolve cross-skill and bundled-asset paths without hardcoded user paths.

The skill bundle can live in three layouts:

1. Repo checkout  — ``<root>/skills/<name>/`` + ``<root>/config/`` + ``<root>/assets/``
2. Flat install   — ``<root>/<name>/`` (e.g. ``~/.codex/skills``, ``~/.agents/skills``)
3. Custom root    — set ``$PODCAST_SKILLS_ROOT`` to whichever layout applies

``skill_dir(name)`` locates a sibling skill (``volcengine-tts``,
``video-shotcraft``, ...) and ``repo_asset(relpath)`` locates a bundled asset
(``assets/bgm/...``, ``assets/sfx/...``). Both never raise: they return
``None`` when nothing matches so callers can fall back or fail loudly.
"""

import os
from pathlib import Path

_LEGACY_ROOTS = (
    Path.home() / ".codex" / "skills",
    Path.home() / ".agents" / "skills",
)


def _candidate_roots(start=None):
    roots = []
    env = os.environ.get("PODCAST_SKILLS_ROOT")
    if env:
        roots.append(Path(env).expanduser())
    cur = Path(start).resolve() if start else Path(__file__).resolve().parent
    roots.extend(cur.parents)
    roots.extend(r for r in _LEGACY_ROOTS if r.is_dir())
    return roots


def skill_dir(name, start=None):
    """Return the install dir of sibling skill ``name``, or ``None``."""
    for root in _candidate_roots(start):
        for cand in (root / "skills" / name, root / name):
            if cand.is_dir():
                return cand
    return None


def repo_asset(relpath, start=None):
    """Return a bundled asset file (``assets/bgm/x.mp3``), or ``None``."""
    for root in _candidate_roots(start):
        for cand in (root / relpath, root / "skills" / relpath):
            if cand.is_file():
                return cand
    return None
