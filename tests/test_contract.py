"""Contract drift guard (Workbench prerequisite 1).

The four types shared verbatim with Endless — `Shape`, `StyleProfile`,
`WorldSeed`, `BeatPlan` — are the round-trip contract. Until they're extracted
into a single shared package, this test makes *structural* drift a loud failure
instead of a silent round-trip break: it compares the live schema of the four
types (field names / types / constraints / required — descriptions ignored)
against a committed snapshot kept byte-identical in both repos.

If this fails and the change is intended: mirror it in Endless, then regenerate
the snapshot in BOTH repos with `python tests/test_contract.py`.
"""

import json
from pathlib import Path

from lit_analyzer.schemas import BeatPlan, Shape, StyleProfile, WorldSeed

_TYPES = (Shape, StyleProfile, WorldSeed, BeatPlan)
_SNAPSHOT = Path(__file__).parent / "contract.schema.json"


def _strip(obj):
    """Drop `description` (docstrings/Field help) so only structure is compared."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "description"}
    if isinstance(obj, list):
        return [_strip(x) for x in obj]
    return obj


def _current() -> dict:
    return {t.__name__: _strip(t.model_json_schema()) for t in _TYPES}


def _snapshot_text() -> str:
    return json.dumps(_current(), indent=2, sort_keys=True) + "\n"


def test_contract_matches_snapshot():
    current = _current()
    snapshot = json.loads(_SNAPSHOT.read_text())
    assert current == snapshot, (
        "The shared contract types drifted from tests/contract.schema.json. "
        "If intended, mirror the change in Endless and regenerate the snapshot in "
        "BOTH repos: `python tests/test_contract.py`."
    )


if __name__ == "__main__":  # regenerate the snapshot
    _SNAPSHOT.write_text(_snapshot_text())
    print(f"wrote {_SNAPSHOT}")
