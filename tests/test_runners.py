from pathlib import Path

import pytest

from var2026.runners.registry import get_runner


@pytest.mark.parametrize("name", ["mip_splatting", "abs_gs", "two_dgs", "gsplat"])
def test_placeholder_methods_fail_clearly(name: str) -> None:
    runner = get_runner(name)
    with pytest.raises(NotImplementedError, match=f"Method {name!r}"):
        runner.train_command(Path("scene"), Path("out"))


def test_graphdeco_train_crosses_environment_boundary() -> None:
    command = get_runner("graphdeco").train_command(Path("/scene"), Path("/run"))
    assert command[:5] == ["conda", "run", "-n", "graphdeco", "python"]
    assert command[-6:] == [
        "-s", "/scene/train",
        "-m", "/run",
        "--iterations", "30000",
    ]


def test_graphdeco_train_accepts_extra_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "VAR2026_GRAPHDECO_EXTRA_ARGS",
        "--densify_until_iter 7000 --data_device cpu",
    )
    command = get_runner("graphdeco").train_command(Path("/scene"), Path("/run"))
    assert command[-4:] == [
        "--densify_until_iter", "7000",
        "--data_device", "cpu",
    ]


def test_graphdeco_inference_uses_test_poses() -> None:
    command = get_runner("graphdeco").infer_command(
        Path("/scene"), Path("/run"), Path("/out")
    )
    assert command[:5] == ["conda", "run", "-n", "graphdeco", "python"]
    assert command[-6:] == [
        "--poses", "/scene/test/test_poses.csv",
        "--run", "/run",
        "--out", "/out",
    ]
