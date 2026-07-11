import pytest

from var2026.camera.colmap_pose import camera_center, quaternion_to_rotation


def test_identity_world_to_camera_center() -> None:
    assert quaternion_to_rotation(1, 0, 0, 0) == (
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
    )
    assert camera_center((1, 0, 0, 0), (1, 2, 3)) == (-1, -2, -3)


def test_zero_quaternion_rejected() -> None:
    with pytest.raises(ValueError, match="nonzero"):
        quaternion_to_rotation(0, 0, 0, 0)
