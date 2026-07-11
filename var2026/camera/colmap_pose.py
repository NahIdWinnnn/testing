import math


def quaternion_to_rotation(
    qw: float, qx: float, qy: float, qz: float
) -> tuple[tuple[float, float, float], ...]:
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm <= 1e-12:
        raise ValueError("Quaternion must be nonzero")
    w, x, y, z = (value / norm for value in (qw, qx, qy, qz))
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def camera_center(
    qvec: tuple[float, float, float, float],
    tvec: tuple[float, float, float],
) -> tuple[float, float, float]:
    rotation = quaternion_to_rotation(*qvec)
    return tuple(
        -sum(rotation[row][column] * tvec[row] for row in range(3))
        for column in range(3)
    )
