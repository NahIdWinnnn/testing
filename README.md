# VAR 2026 Novel View Synthesis

Repo này là lớp điều phối cho VAR 2026 Novel View Synthesis / BTS Digital Twin.
GraphDeCo vẫn là backend 3D Gaussian Splatting chính; code trong `var2026/`
chủ yếu lo data contract của cuộc thi, chạy lệnh, QA, visualization và
submission.

README này dành cho người đã có dữ liệu `VAI_NVS_DATA/` và model GraphDeCo đã
train trong `runs/`. Nếu cần train hoặc reproduce đầy đủ, xem
[[docs/reproducibility.md]].

## Thư mục

```text
Novel-View-Synthesis/
├── VAI_NVS_DATA/   dữ liệu cuộc thi, Git bỏ qua
├── runs/           model đã train và render, Git bỏ qua
├── submissions/    file nộp, Git bỏ qua
├── methods/        external implementations: GraphDeCo, SIBR
└── var2026/        orchestration, QA, validation, adapters
```

Mỗi scene contest có:

```text
<scene>/
├── train/images
├── train/sparse/0/{cameras.bin,images.bin,points3D.bin}
└── test/test_poses.csv
```

Pose trong `test_poses.csv` là COLMAP world-to-camera. Không tự đảo pose. Xem
[[docs/camera_convention.md]].

## Cài Đặt Nhẹ

Luồng này đủ để chạy CLI, test, validate submission và mở SIBR viewer với model
đã train.

Trên workstation/WSL đã có Conda, cách nhanh nhất cho anh em trong team:

```bash
git clone <repository-url> Novel-View-Synthesis
cd Novel-View-Synthesis
cp .env.example .env
scripts/setup.sh
scripts/setup_sibr.sh --native
just test
just viz graphdeco
```

`scripts/setup.sh` cài system packages cơ bản, tạo/cập nhật env `var2026`, tạo
env method `graphdeco`, cài CUDA toolkit trong env GraphDeCo và build extension
upstream. `scripts/setup_sibr.sh --native` build viewer có panel `VAR Test Poses`
và phím Left/Right.

Nếu chỉ cần env orchestration nhẹ:

```bash
git clone <repository-url> Novel-View-Synthesis
cd Novel-View-Synthesis
cp .env.example .env
conda env create -f envs/var2026.yml
conda run -n var2026 python -m var2026 --help
```

Nếu env `var2026` đã tồn tại:

```bash
conda env update -n var2026 -f envs/var2026.yml --prune
```

Native SIBR build trên WSL/Linux cần các package hệ thống này nếu chưa có:

```bash
sudo apt update
sudo apt install -y cmake ninja-build libglew-dev libassimp-dev \
  libboost-all-dev libgtk-3-dev libopencv-dev libglfw3-dev \
  libavdevice-dev libavcodec-dev libeigen3-dev libxxf86vm-dev libembree-dev
```

Mặc định repo tìm dữ liệu ở `VAI_NVS_DATA/phase1/private_set1` và model ở
`runs/graphdeco/<scene>`. Có thể sửa `.env` nếu cần.

## Colab Outputs

Nếu train/render trên Colab, dùng notebook
[[notebooks/colab_graphdeco_train_render.ipynb]]. Archive export từ Colab giải
nén vào `runs/`:

```bash
mkdir -p runs
tar -xzf <scene>_graphdeco_colab_export.tar.gz -C runs
```

Sau khi giải nén, repo mong đợi:

```text
runs/graphdeco/<scene>/point_cloud/iteration_<N>/point_cloud.ply
runs/graphdeco/<scene>/renders_test/<image_name>
runs/_prepared/graphdeco/<scene>/test/test_poses.csv
```

Trong đó `point_cloud.ply` là weight/model GraphDeCo đã train, còn
`renders_test/` là ảnh test đã render từ Colab.

Để xem nhanh một model Colab chưa muốn đưa vào layout method chuẩn, có thể đặt
model trực tiếp ở:

```text
runs/<scene>/point_cloud/iteration_<N>/point_cloud.ply
runs/<scene>/test/test_poses.csv        # optional
```

Khi đó `just viz <scene>` vẫn resolve được scene đó bằng default method
`graphdeco`.

## Visualization

Model GraphDeCo đã train là file:

```text
runs/graphdeco/<scene>/point_cloud/iteration_*/point_cloud.ply
```

`GaussianModel.load_ply(...)` load file `.ply` này. Đây là output của training
GraphDeCo, không phải model tự train trong `var2026`.

Cài SIBR viewer:

```bash
scripts/setup_sibr.sh
```

Trên WSL, script tải Windows binary chính thức của GraphDeCo vào `.local/`.
Đây là `raw-sibr-fallback`: mở được model thô, nhưng không có VAR Test Poses
panel.

Nếu muốn Left/Right nhảy theo `test/test_poses.csv`, cần native viewer đã patch:

```bash
scripts/setup_sibr.sh --native
```

Native build sẽ apply patch trong `docs/patches/` rồi build
`methods/sibr_viewers`. Sau đó mở scene selector:

```bash
just viz graphdeco
```

Bảng sẽ liệt kê các scene đã có model trong `runs/graphdeco/<scene>` hoặc
`runs/<scene>`. Nhập số thứ tự hoặc tên scene để mở viewer.

Muốn mở thẳng một scene:

```bash
just viz <scene>
just viz <scene> graphdeco
```

Nếu chưa có `just`, dùng trực tiếp CLI:

```bash
conda run --no-capture-output -n var2026 python -m var2026 viz graphdeco \
  --runs-root runs \
  --prepared-root runs/_prepared/graphdeco
```

`viz` cần:

- model đã train ở `runs/graphdeco/<scene>` hoặc `runs/<scene>`
- nếu dùng test-pose navigation: `runs/_prepared/graphdeco/<scene>/test/test_poses.csv`,
  hoặc `runs/<scene>/test/test_poses.csv`

Muốn cố mở raw viewer khi scene có test poses:

```bash
VAR2026_SIBR_ALLOW_RAW=1 just viz <scene>
```

## Inference Và Submission

Inference contest không dùng trực tiếp `methods/graphdeco/render.py`. Repo dùng
adapter [var2026/runners/graphdeco_render.py](var2026/runners/graphdeco_render.py)
để đọc `test_poses.csv`, dựng camera GraphDeCo, gọi renderer upstream, rồi save
ảnh đúng format cuộc thi.

Các lệnh thường dùng khi đã có env/method đầy đủ:

```bash
just infer <scene> graphdeco
just validate round1_v001
just submit graphdeco round1_v001
```

`infer` cần env method `graphdeco` vì nó load PyTorch/CUDA GraphDeCo. Cách dựng
env đó nằm trong [[docs/reproducibility.md]].

## Test Nhanh

```bash
just test
```

Nếu chưa có `just`:

```bash
conda run -n var2026 python -m pytest
```

Test chỉ dùng env `var2026`, không train model.

## Tài Liệu

- [[docs/reproducibility.md]]: train/infer/submit lại một run đầy đủ.
- [[docs/camera_convention.md]]: quy ước camera, quaternion, translation.
- [[docs/graphdeco_patch_log.md]]: patch đã đụng tới GraphDeCo/SIBR.
- [[docs/shared_gpu_workstation.md]]: setup máy GPU dùng chung.
- [[notebooks/README.md]]: notebook Colab và output contract.

`AGENTS.md` và `CLAUDE.md` là quy tắc cho công cụ AI, người chạy pipeline không
cần đọc.
