# Camera convention

`test_poses.csv` stores COLMAP world-to-camera poses. Quaternion order is
`qw,qx,qy,qz`; translation order is `tx,ty,tz`. The camera center is
`C = -R.T @ t`. Local axes are x right, y down, z forward.

No shared parser or runner may silently reinterpret these as camera-to-world.
Backend-specific conversion must be explicit, tested, and documented.
