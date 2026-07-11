import math


def focal_to_fov(focal: float, pixels: int) -> float:
    if focal <= 0 or pixels <= 0:
        raise ValueError("Focal length and image dimension must be positive")
    return 2.0 * math.atan(pixels / (2.0 * focal))
