import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run_command(command: list[str], output: Path, metadata: dict[str, object]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "run.log"
    metadata_path = output / "run.json"
    record = {
        **metadata,
        "command": command,
        "command_display": shlex.join(command),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "log": str(log_path),
    }
    metadata_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    try:
        with log_path.open("a", encoding="utf-8") as log:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        record["returncode"] = result.returncode
        record["status"] = "succeeded" if result.returncode == 0 else "failed"
        if result.returncode:
            record["error"] = f"Command exited with status {result.returncode}"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if record["status"] != "succeeded":
        raise RuntimeError(str(record["error"]))
