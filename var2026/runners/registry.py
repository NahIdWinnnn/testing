from var2026.runners.base import MethodRunner
from var2026.runners.graphdeco_runner import GraphDeCoRunner
from var2026.runners.placeholders import PlaceholderRunner


def get_runner(name: str) -> MethodRunner:
    if name == "graphdeco":
        return GraphDeCoRunner()
    if name in {"mip_splatting", "abs_gs", "two_dgs", "gsplat"}:
        return PlaceholderRunner(name)
    raise ValueError(f"Unknown method {name!r}")
