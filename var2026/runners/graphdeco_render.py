import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GRAPHDECO = ROOT / "methods" / "graphdeco"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(GRAPHDECO))

from gaussian_renderer import GaussianModel, render  # noqa: E402
from scene.cameras import MiniCam  # noqa: E402
from utils.graphics_utils import getProjectionMatrix, getWorld2View2  # noqa: E402
from var2026.camera.colmap_pose import quaternion_to_rotation  # noqa: E402
from var2026.camera.fov import focal_to_fov  # noqa: E402
from var2026.io.test_poses import load_test_poses  # noqa: E402


def latest_model(run: Path) -> Path:
    models = sorted(
        run.glob("point_cloud/iteration_*/point_cloud.ply"),
        key=lambda path: int(path.parent.name.removeprefix("iteration_")),
    )
    if not models:
        raise RuntimeError(f"No trained model found in {run}")
    return models[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poses", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    poses = load_test_poses(args.poses)
    args.out.mkdir(parents=True, exist_ok=True)
    model = latest_model(args.run)
    gaussians = GaussianModel(3)
    gaussians.load_ply(str(model))
    pipeline = SimpleNamespace(
        convert_SHs_python=False,
        compute_cov3D_python=False,
        debug=False,
        antialiasing=False,
    )
    background = torch.zeros(3, dtype=torch.float32, device="cuda")

    with torch.no_grad():
        for index, pose in enumerate(poses, start=1):
            if abs(pose.cx - pose.width / 2) > 1e-6 or abs(
                pose.cy - pose.height / 2
            ) > 1e-6:
                raise RuntimeError(
                    f"{pose.image_name}: off-center principal point is unsupported"
                )
            rotation_w2c = np.asarray(
                quaternion_to_rotation(pose.qw, pose.qx, pose.qy, pose.qz)
            )
            translation = np.asarray((pose.tx, pose.ty, pose.tz))
            fov_x = focal_to_fov(pose.fx, pose.width)
            fov_y = focal_to_fov(pose.fy, pose.height)
            world_view = torch.tensor(
                getWorld2View2(rotation_w2c.T, translation)
            ).transpose(0, 1).cuda()
            projection = getProjectionMatrix(
                znear=0.01,
                zfar=100.0,
                fovX=fov_x,
                fovY=fov_y,
            ).transpose(0, 1).cuda()
            camera = MiniCam(
                pose.width,
                pose.height,
                fov_y,
                fov_x,
                0.01,
                100.0,
                world_view,
                world_view.unsqueeze(0).bmm(projection.unsqueeze(0)).squeeze(0),
            )
            image = render(
                camera,
                gaussians,
                pipeline,
                background,
                separate_sh=False,
            )["render"]
            pixels = (
                image.mul(255)
                .clamp(0, 255)
                .byte()
                .permute(1, 2, 0)
                .cpu()
                .numpy()
            )
            Image.fromarray(pixels).save(args.out / pose.image_name, quality=95)
            print(f"[{index}/{len(poses)}] {pose.image_name}", flush=True)


if __name__ == "__main__":
    main()
