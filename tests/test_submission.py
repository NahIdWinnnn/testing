from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from var2026.submission.make_zip import make_submission_zip
from var2026.submission.validate import validate_submission

HEADER = "image_name,qw,qx,qy,qz,tx,ty,tz,fx,fy,cx,cy,width,height\n"
ROW = "view.png,1,0,0,0,0,0,0,100,100,2,1,4,2\n"


def make_scene(root: Path) -> None:
    pose_dir = root / "scene_001" / "test"
    pose_dir.mkdir(parents=True)
    (pose_dir / "test_poses.csv").write_text(HEADER + ROW)


def test_valid_submission_and_zip_root(tmp_path: Path) -> None:
    data = tmp_path / "data"
    submission = tmp_path / "submission"
    make_scene(data)
    output = submission / "scene_001"
    output.mkdir(parents=True)
    Image.new("RGB", (4, 2)).save(output / "view.png")
    result = validate_submission(data, submission)
    assert result.valid

    archive_path = tmp_path / "submission.zip"
    make_submission_zip(submission, archive_path)
    with ZipFile(archive_path) as archive:
        assert archive.namelist() == ["scene_001/view.png"]


def test_wrong_size_and_extra_file_fail(tmp_path: Path) -> None:
    data = tmp_path / "data"
    submission = tmp_path / "submission"
    make_scene(data)
    output = submission / "scene_001"
    output.mkdir(parents=True)
    Image.new("RGB", (3, 2)).save(output / "view.png")
    (output / "extra.txt").write_text("no")
    result = validate_submission(data, submission)
    assert not result.valid
    assert any("size 3x2" in error for error in result.errors)
    assert any("extra image extra.txt" in error for error in result.errors)


def test_missing_scene_fails(tmp_path: Path) -> None:
    data = tmp_path / "data"
    submission = tmp_path / "submission"
    make_scene(data)
    submission.mkdir()
    result = validate_submission(data, submission)
    assert not result.valid
    assert "Missing scene directory: scene_001" in result.errors
