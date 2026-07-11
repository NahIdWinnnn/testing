from pathlib import Path

import pytest

from var2026.io.test_poses import load_test_poses

HEADER = "image_name,qw,qx,qy,qz,tx,ty,tz,fx,fy,cx,cy,width,height\n"


def test_load_valid_pose(tmp_path: Path) -> None:
    path = tmp_path / "test_poses.csv"
    path.write_text(HEADER + "test.png,1,0,0,0,1,2,3,500,500,320,240,640,480\n")
    pose = load_test_poses(path)[0]
    assert pose.image_name == "test.png"
    assert (pose.width, pose.height) == (640, 480)
    assert (pose.qw, pose.tx) == (1, 1)


@pytest.mark.parametrize(
    "row,match",
    [
        ("../test.png,1,0,0,0,0,0,0,1,1,0,0,10,10\n", "plain filename"),
        ("test.png,0,0,0,0,0,0,0,1,1,0,0,10,10\n", "nonzero"),
        ("test.png,1,0,0,0,0,0,0,nan,1,0,0,10,10\n", "finite"),
        ("test.png,1,0,0,0,0,0,0,1,1,0,0,10.5,10\n", "positive integer"),
    ],
)
def test_invalid_pose_rejected(tmp_path: Path, row: str, match: str) -> None:
    path = tmp_path / "test_poses.csv"
    path.write_text(HEADER + row)
    with pytest.raises(ValueError, match=match):
        load_test_poses(path)


def test_duplicate_name_rejected(tmp_path: Path) -> None:
    path = tmp_path / "test_poses.csv"
    row = "test.png,1,0,0,0,0,0,0,1,1,0,0,10,10\n"
    path.write_text(HEADER + row + row)
    with pytest.raises(ValueError, match="duplicate"):
        load_test_poses(path)
