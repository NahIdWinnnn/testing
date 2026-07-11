import os
from pathlib import Path

import typer

from var2026.io.scene_layout import SceneLayout
from var2026.preprocess.graphdeco import prepare_graphdeco_scene
from var2026.runners.execution import run_command
from var2026.runners.registry import get_runner
from var2026.submission.collect import collect_renders
from var2026.submission.make_zip import make_submission_zip
from var2026.submission.validate import validate_submission, write_validation_result
from var2026.viewer.sibr import (
    SibrSceneSummary,
    bundle_viewer,
    list_sibr_scenes,
    launch_sibr_viewer,
    resolve_sibr_scene,
    viewer_from_env,
)

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)


@app.command("prepare-graphdeco")
def prepare_graphdeco(
    scene: Path = typer.Option(..., exists=True, file_okay=False),
    out: Path = typer.Option(...),
    colmap: str = typer.Option("colmap"),
) -> None:
    try:
        rebuilt = prepare_graphdeco_scene(scene, out, colmap)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"{'Prepared' if rebuilt else 'Using cached'}: {out}")


@app.command()
def train(
    method: str = typer.Option(...),
    scene: Path = typer.Option(..., exists=True, file_okay=False),
    out: Path = typer.Option(...),
) -> None:
    layout = SceneLayout(scene.resolve())
    layout.validate()
    runner = get_runner(method)
    command = runner.train_command(layout.root, out.resolve())
    run_command(
        command,
        out.resolve(),
        {
            "method": method,
            "scene": layout.name,
            "operation": "train",
            "config": {"scene": str(layout.root), "output": str(out.resolve())},
        },
    )


@app.command()
def infer(
    method: str = typer.Option(...),
    scene: Path = typer.Option(..., exists=True, file_okay=False),
    run: Path = typer.Option(..., exists=True, file_okay=False),
    out: Path = typer.Option(...),
) -> None:
    layout = SceneLayout(scene.resolve())
    layout.validate()
    runner = get_runner(method)
    command = runner.infer_command(layout.root, run.resolve(), out.resolve())
    run_command(
        command,
        run.resolve(),
        {
            "method": method,
            "scene": layout.name,
            "operation": "infer",
            "config": {
                "scene": str(layout.root),
                "run": str(run.resolve()),
                "output": str(out.resolve()),
            },
        },
    )


@app.command("infer-submit")
def infer_submit(
    method: str = typer.Option(...),
    data_root: Path = typer.Option(..., exists=True, file_okay=False),
    runs_root: Path = typer.Option(..., exists=True, file_okay=False),
    submission_dir: Path = typer.Option(...),
    zip_out: Path = typer.Option(...),
) -> None:
    get_runner(method)
    collect_renders(data_root.resolve(), runs_root.resolve(), submission_dir.resolve())
    result = validate_submission(data_root.resolve(), submission_dir.resolve())
    report = submission_dir.resolve().with_name(submission_dir.name + "_validation.json")
    write_validation_result(result, report)
    if not result.valid:
        for error in result.errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    make_submission_zip(submission_dir.resolve(), zip_out.resolve())
    typer.echo(f"Created valid submission: {zip_out}")


@app.command("validate-submission")
def validate_submission_command(
    data_root: Path = typer.Option(..., exists=True, file_okay=False),
    submission_dir: Path = typer.Option(..., file_okay=False),
) -> None:
    result = validate_submission(data_root.resolve(), submission_dir.resolve())
    report = submission_dir.resolve().with_name(submission_dir.name + "_validation.json")
    write_validation_result(result, report)
    if not result.valid:
        for error in result.errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    typer.echo(f"Valid: {result.scenes} scene(s), {result.images} image(s). Report: {report}")


@app.command("viz")
def viz(
    target: str | None = typer.Argument(None),
    maybe_method: str | None = typer.Argument(None),
    runs_root: Path = typer.Option(Path("runs"), file_okay=False),
    prepared_root: Path = typer.Option(Path("runs/_prepared/graphdeco"), file_okay=False),
) -> None:
    try:
        scene, method = _resolve_viz_target(target, maybe_method, runs_root.resolve())
        if scene is None:
            scene = _select_sibr_scene(method, runs_root.resolve(), prepared_root.resolve())
        paths = resolve_sibr_scene(
            scene,
            method,
            runs_root.resolve(),
            prepared_root.resolve(),
        )
        returncode = launch_sibr_viewer(
            paths,
            viewer_from_env(),
            extra_args=os.environ.get("VAR2026_SIBR_EXTRA_ARGS", ""),
        )
    except (EOFError, KeyboardInterrupt):
        typer.echo("Cancelled.", err=True)
        raise typer.Exit(1)
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if returncode:
        raise typer.Exit(returncode)


def _resolve_viz_target(
    target: str | None,
    maybe_method: str | None,
    runs_root: Path,
) -> tuple[str | None, str]:
    default_method = os.environ.get("VAR2026_DEFAULT_METHOD", "graphdeco")
    known_methods = {default_method, "graphdeco"}
    if runs_root.is_dir():
        known_methods.update(child.name for child in runs_root.iterdir() if child.is_dir())
    if target is None:
        return None, default_method
    if maybe_method is not None:
        return target, maybe_method
    if target in known_methods:
        return None, target
    return target, default_method


def _select_sibr_scene(method: str, runs_root: Path, prepared_root: Path) -> str:
    scenes = list_sibr_scenes(method, runs_root, prepared_root)
    if not scenes:
        raise FileNotFoundError(f"No valid {method} scenes found under {runs_root / method} or {runs_root}")
    _print_sibr_scene_table(scenes)
    choice = input("Select scene number/name: ").strip()
    if not choice:
        raise ValueError("No scene selected")
    if choice.isdigit():
        index = int(choice)
        if index < 1 or index > len(scenes):
            raise ValueError(f"Scene number out of range: {choice}")
        return scenes[index - 1].scene
    by_name = {scene.scene: scene for scene in scenes}
    if choice not in by_name:
        raise ValueError(f"Unknown scene: {choice}")
    return choice


def _print_sibr_scene_table(scenes: list[SibrSceneSummary]) -> None:
    rows = [
        (
            str(index),
            scene.scene,
            "yes" if scene.test_poses is not None else "no",
            str(scene.test_camera_count),
            scene.layout,
        )
        for index, scene in enumerate(scenes, start=1)
    ]
    headers = ("#", "scene", "test_poses", "count", "layout")
    widths = [
        max(len(headers[column]), *(len(row[column]) for row in rows))
        for column in range(len(headers))
    ]
    typer.echo("Available SIBR scenes:")
    typer.echo("  " + "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    typer.echo("  " + "  ".join("-" * width for width in widths))
    for row in rows:
        typer.echo("  " + "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


@app.command("sibr-view")
def sibr_view(
    scene: str = typer.Option(...),
    method: str = typer.Option("graphdeco"),
    runs_root: Path = typer.Option(Path("runs"), file_okay=False),
    prepared_root: Path = typer.Option(Path("runs/_prepared/graphdeco"), file_okay=False),
    data_root: Path | None = typer.Option(None, file_okay=False),
) -> None:
    try:
        if data_root is not None:
            SceneLayout((data_root / scene).resolve()).validate()
        paths = resolve_sibr_scene(
            scene,
            method,
            runs_root.resolve(),
            prepared_root.resolve(),
        )
        returncode = launch_sibr_viewer(
            paths,
            viewer_from_env(),
            extra_args=os.environ.get("VAR2026_SIBR_EXTRA_ARGS", ""),
        )
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if returncode:
        raise typer.Exit(returncode)


@app.command("bundle-viewer")
def bundle_viewer_command(
    scene: str = typer.Option(...),
    out: Path = typer.Option(...),
    method: str = typer.Option("graphdeco"),
    runs_root: Path = typer.Option(Path("runs"), file_okay=False),
    prepared_root: Path = typer.Option(Path("runs/_prepared/graphdeco"), file_okay=False),
    data_root: Path | None = typer.Option(None, file_okay=False),
) -> None:
    try:
        if data_root is not None:
            SceneLayout((data_root / scene).resolve()).validate()
        paths = resolve_sibr_scene(
            scene,
            method,
            runs_root.resolve(),
            prepared_root.resolve(),
        )
        bundle = bundle_viewer(paths, out)
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(str(bundle))
