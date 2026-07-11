# Colab Notebooks

Notebook chính:

- [[colab_graphdeco_train_render.ipynb]]: train GraphDeCo và render test poses
  trên Colab, rồi export một archive đem về repo local.

## Output Contract

Với scene `<scene>`, archive từ Colab phải giải nén vào `runs/` và tạo đúng các
đường dẫn:

```text
runs/
├── graphdeco/<scene>/
│   ├── point_cloud/iteration_<N>/point_cloud.ply
│   └── renders_test/<image_name>
└── _prepared/graphdeco/<scene>/
    └── test/test_poses.csv
```

Ý nghĩa:

- `point_cloud/iteration_<N>/point_cloud.ply`: weight/model GraphDeCo đã train.
- `renders_test/`: ảnh render từ `test/test_poses.csv`, đúng tên file trong CSV.
- `_prepared/.../test/test_poses.csv`: bản copy test poses để local viewer biết
  camera test nào cần nhảy tới.

Nếu muốn dùng SIBR visualization local, local repo vẫn cần prepared train source:

```bash
conda run -n var2026 python -m var2026 prepare-graphdeco \
  --scene VAI_NVS_DATA/phase1/private_set1/<scene> \
  --out runs/_prepared/graphdeco/<scene>
```

Sau khi copy archive về repo local:

```bash
mkdir -p runs
tar -xzf <scene>_graphdeco_colab_export.tar.gz -C runs
```

Kiểm tra render/submission:

```bash
just validate round1_v001
just submit graphdeco round1_v001
```
