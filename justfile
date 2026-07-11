set dotenv-load

repo_root := justfile_directory()
data_root := env_var_or_default("VAR2026_DATA_ROOT", repo_root + "/VAI_NVS_DATA/phase1/private_set1")
public_data_root := env_var_or_default("VAR2026_PUBLIC_DATA_ROOT", repo_root + "/VAI_NVS_DATA/phase1/public_set")
runs_root := env_var_or_default("VAR2026_RUNS_ROOT", repo_root + "/runs")
submissions_root := env_var_or_default("VAR2026_SUBMISSIONS_ROOT", repo_root + "/submissions")
prepared_root := runs_root + "/_prepared/graphdeco"
default_method := env_var_or_default("VAR2026_DEFAULT_METHOD", "graphdeco")

default:
    @just --list

setup:
    scripts/setup.sh

doctor:
    scripts/doctor.sh

gpu:
    nvidia-smi

watch-gpu:
    watch -n 1 nvidia-smi

train scene method=default_method:
    conda run -n var2026 python -m var2026 prepare-graphdeco --scene {{data_root}}/{{scene}} --out {{prepared_root}}/{{scene}}
    conda run -n var2026 python -m var2026 train --method {{method}} --scene {{prepared_root}}/{{scene}} --out {{runs_root}}/{{method}}/{{scene}}

train-public scene method=default_method:
    conda run -n var2026 python -m var2026 prepare-graphdeco --scene {{public_data_root}}/{{scene}} --out {{prepared_root}}/{{scene}}
    conda run -n var2026 python -m var2026 train --method {{method}} --scene {{prepared_root}}/{{scene}} --out {{runs_root}}/{{method}}/{{scene}}

infer scene method=default_method:
    conda run -n var2026 python -m var2026 infer --method {{method}} --scene {{data_root}}/{{scene}} --run {{runs_root}}/{{method}}/{{scene}} --out {{runs_root}}/{{method}}/{{scene}}/renders_test

infer-public scene method=default_method:
    conda run -n var2026 python -m var2026 infer --method {{method}} --scene {{public_data_root}}/{{scene}} --run {{runs_root}}/{{method}}/{{scene}} --out {{runs_root}}/{{method}}/{{scene}}/renders_test

submit method=default_method version="round1_v001":
    conda run -n var2026 python -m var2026 infer-submit --method {{method}} --data-root {{data_root}} --runs-root {{runs_root}}/{{method}} --submission-dir {{submissions_root}}/{{version}} --zip-out {{submissions_root}}/submission_{{version}}.zip

validate version="round1_v001":
    conda run -n var2026 python -m var2026 validate-submission --data-root {{data_root}} --submission-dir {{submissions_root}}/{{version}}

viz target=default_method method="":
    conda run --no-capture-output -n var2026 python -m var2026 viz {{target}} {{method}} --runs-root {{runs_root}} --prepared-root {{prepared_root}}

test:
    conda run -n var2026 python -m pytest
