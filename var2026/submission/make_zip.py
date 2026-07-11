from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def make_submission_zip(submission_dir: Path, zip_out: Path) -> None:
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_out, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(submission_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(submission_dir))
