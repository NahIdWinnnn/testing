import csv
import math
from dataclasses import dataclass
from pathlib import Path, PurePath

EXPECTED_COLUMNS = (
    "image_name",
    "qw", "qx", "qy", "qz",
    "tx", "ty", "tz",
    "fx", "fy", "cx", "cy",
    "width", "height",
)


@dataclass(frozen=True)
class TestPose:
    __test__ = False

    image_name: str
    qw: float
    qx: float
    qy: float
    qz: float
    tx: float
    ty: float
    tz: float
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


def _finite_float(row: dict[str, str], name: str, line: int) -> float:
    try:
        value = float(row[name])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Line {line}: {name} is not a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"Line {line}: {name} must be finite")
    return value


def _positive_int(row: dict[str, str], name: str, line: int) -> int:
    value = _finite_float(row, name, line)
    if not value.is_integer() or value <= 0:
        raise ValueError(f"Line {line}: {name} must be a positive integer")
    return int(value)


def load_test_poses(path: Path) -> list[TestPose]:
    if not path.is_file():
        raise ValueError(f"Test poses CSV does not exist: {path}")
    poses: list[TestPose] = []
    names: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected columns in {path}; expected {','.join(EXPECTED_COLUMNS)}"
            )
        for line, row in enumerate(reader, start=2):
            name = (row["image_name"] or "").strip()
            pure = PurePath(name)
            if not name or pure.name != name or name in {".", ".."}:
                raise ValueError(f"Line {line}: image_name must be a plain filename")
            if name in names:
                raise ValueError(f"Line {line}: duplicate image_name {name!r}")
            values = {
                key: _finite_float(row, key, line)
                for key in EXPECTED_COLUMNS[1:-2]
            }
            quaternion_norm = math.sqrt(sum(values[key] ** 2 for key in ("qw", "qx", "qy", "qz")))
            if quaternion_norm <= 1e-12:
                raise ValueError(f"Line {line}: quaternion must be nonzero")
            if values["fx"] <= 0 or values["fy"] <= 0:
                raise ValueError(f"Line {line}: fx and fy must be positive")
            names.add(name)
            poses.append(
                TestPose(
                    image_name=name,
                    **values,
                    width=_positive_int(row, "width", line),
                    height=_positive_int(row, "height", line),
                )
            )
    if not poses:
        raise ValueError(f"No test poses found in {path}")
    return poses
