# Reproduce a run

File này dành cho luồng nặng: train, infer và tạo submission sao cho teammate
hoặc judge có thể chạy lại. Nếu chỉ cần mở trained scene hoặc validate nhẹ, xem
[[../README.md]].

## Cần Lưu Gì

Mỗi submission cần lưu:

```text
repo commit
config và method
env hoặc package list
lệnh train, infer, submit
log và validation report
model, render và ZIP
```

Thư mục gợi ý:

```text
runs/<method>/<scene>/
├── config.yaml
├── command_train.sh
├── command_infer.sh
├── train.log
├── infer.log
├── model/
├── renders_test/
└── metadata.json
```

Lưu phiên bản code và env:

```bash
git rev-parse HEAD
conda env export -n var2026 --no-builds > var2026.yml
conda env export -n graphdeco --no-builds > graphdeco.yml
```

Nếu sửa method, commit luôn file trong `methods/graphdeco`.

Lưu log:

```bash
just train <scene> graphdeco 2>&1 | tee train.log
just infer <scene> graphdeco 2>&1 | tee infer.log
just validate round1_v001
```

Thành công khi mọi lệnh exit `0` và validation in `Valid:`. Nếu lỗi, giữ log và
dừng. Không bỏ qua scene. Không giảm kiểm tra validation.

Khi chạy lại: checkout đúng commit, tạo đúng env, đặt data/model đúng path, rồi
chạy đúng các lệnh đã lưu.

## Env Đầy Đủ

Repo tách env thành hai phần:

- `var2026`: orchestration, QA, validation, submission.
- `graphdeco`: method env có PyTorch/CUDA và CUDA extensions để train/infer
  GraphDeCo.

Setup đầy đủ:

```bash
cp .env.example .env
bash scripts/setup.sh
just doctor
```

`scripts/setup.sh` sẽ:

1. cài system packages cần thiết như COLMAP và `just`
2. tạo/update env `var2026`
3. tạo/update env `graphdeco`
4. build GraphDeCo CUDA extensions
5. chạy `scripts/doctor.sh`

File `methods/graphdeco/environment.yml` là upstream reference của GraphDeCo.
Repo này dùng env method canonical tên `graphdeco`, được tạo trong
`scripts/setup.sh`.

## Train Lại GraphDeCo

GraphDeCo là black box training chính. `var2026` chỉ chuẩn hóa input rồi gọi
`methods/graphdeco/train.py`.

```bash
just train-public hcm0031 graphdeco
just train <scene> graphdeco
```

Trước khi train, `prepare-graphdeco` dùng COLMAP để undistort camera
`SIMPLE_RADIAL`, lưu cache ở:

```text
runs/_prepared/graphdeco/<scene>/
```

Dataset gốc trong `VAI_NVS_DATA/` không bị sửa.

Model train xong nằm ở:

```text
runs/graphdeco/<scene>/point_cloud/iteration_*/point_cloud.ply
```

Đây là file được `GaussianModel.load_ply(...)` load khi inference hoặc mở
viewer.

## Infer Và Submit Lại

```bash
just infer <scene> graphdeco
just submit graphdeco round1_v001
just validate round1_v001
```

Inference contest đi qua `var2026/runners/graphdeco_render.py`, không đi trực
tiếp qua `methods/graphdeco/render.py`, vì VAR dùng `test/test_poses.csv` riêng.
Adapter này chỉ dựng camera từ CSV rồi gọi renderer upstream của GraphDeCo.

Validation phải giữ strict: đủ scene, đủ ảnh, đúng tên, đúng kích thước, decode
được ảnh, không file thừa. Không giảm validation để submission pass.

## Nhập Kết Quả Từ Colab

Notebook [[../notebooks/colab_graphdeco_train_render.ipynb]] train và render
một scene trên Colab, rồi export archive có layout dành cho `runs/`.

Giải nén tại repo local:

```bash
mkdir -p runs
tar -xzf <scene>_graphdeco_colab_export.tar.gz -C runs
```

Các file cần có sau khi import:

```text
runs/graphdeco/<scene>/point_cloud/iteration_<N>/point_cloud.ply
runs/graphdeco/<scene>/renders_test/<image_name>
runs/_prepared/graphdeco/<scene>/test/test_poses.csv
```

Nếu Colab đã render đủ `renders_test/`, local không cần chạy `just infer` cho
scene đó nữa; chỉ cần collect/validate/submit. Nếu muốn mở SIBR viewer local,
chạy lại prepare để có `runs/_prepared/graphdeco/<scene>/train`.
