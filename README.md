# EthosGuard ROS 2 command-supervisor MRE

Minimal demonstration of a ROS 2 command-supervision idea: an intermediate node
between a command producer and a downstream consumer that forwards commands
passing validation and blocks commands when freshness or value checks fail.

**This is a demo, not a safety component.** The tests below do not establish
that this can safely stop a physical robot. There is no safety certification
here. The repository contains only this demonstration node, reproduction
instructions, and test evidence — not the full EthosGuard implementation.

## Interface

- Node: `ethosguard_mre`
- Subscribes: `/ethosguard_demo/raw` (`geometry_msgs/msg/Twist`, queue depth 1)
- Publishes: `/ethosguard_demo/checked` (`geometry_msgs/msg/Twist`, queue depth 1),
  on a 20 Hz timer
- Per-command validation: 6 finite components, |linear| ≤ 0.5 m/s,
  |angular| ≤ 1.0 rad/s (illustrative bounds, not robot-specific limits)
- Modes: `NOMINAL` (pass through) / `DEGRADED` (invalid command → zero output)
  / `STALE` (> 0.5 s without input → zero output, clears on fresh valid input)
  / `FAIL_SAFE` (two consecutive invalid commands latch → zero output until
  the process is restarted). Mode changes are logged.

## Requirements

- Ubuntu 24.04, ROS 2 Jazzy (`ros-jazzy-ros-base`), `rclpy`, `geometry_msgs`
- The Python interpreter matching the ROS installation (normally `/usr/bin/python3`)

## Reproduction

Use an otherwise unused ROS domain; no other publishers should use the demo topics.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=81
```

Logic self-test (no ROS needed — pure decision logic):

```bash
/usr/bin/python3 ethosguard_ros2_mre.py --self-test
# expected: PASS: startup, forwarding, timeout, NaN, bounds, latch (exit 0)
```

Shutdown smoke test (needs ROS):

```bash
/usr/bin/python3 test_ros_shutdown.py
# expected: ROS_SHUTDOWN_PASS: STALE observed, SIGTERM exit 0, no traceback
```

Transport test (needs ROS with working DDS networking):

```bash
/usr/bin/python3 test_ros_transport.py
# expected: ROS_TRANSPORT_PASS (exit 0)
```

Manual run — terminal 1:

```bash
python3 ethosguard_ros2_mre.py
```

Terminal 2:

```bash
ros2 topic echo /ethosguard_demo/checked geometry_msgs/msg/Twist
```

Terminal 3, valid commands at 10 Hz:

```bash
ros2 topic pub --rate 10 /ethosguard_demo/raw geometry_msgs/msg/Twist '{linear: {x: 0.2}}'
```

Expected: `linear.x: 0.2` on `/ethosguard_demo/checked`. Stop the publisher:
after the 0.5 s receive timeout the output goes to zero. Then publish an
out-of-bounds command:

```bash
ros2 topic pub --rate 10 /ethosguard_demo/raw geometry_msgs/msg/Twist '{linear: {x: 0.6}}'
```

Expected: first invalid message → `DEGRADED`, second → latched `FAIL_SAFE`.
Stop it and send the valid command again: output stays zero until restart.

## Test status (honest)

Recorded environment: Ubuntu 24.04.5 LTS, Python 3.12.3, ROS 2 Jazzy
(`ros-jazzy-ros-base` 0.11.0), `rclpy` 7.1.12, default RMW
(`rmw_fastrtps_cpp` 8.4.4; `rmw_cyclonedds_cpp` 2.2.4 also attempted),
`ROS_DOMAIN_ID=81`.

- `ethosguard_ros2_mre.py --self-test` → **PASS** (exit 0), against real
  `rclpy`, no mocks.
- `test_ros_shutdown.py` → **PASS** (exit 0): STALE observed, clean SIGTERM,
  no traceback.
- `test_ros_transport.py` → **FAIL** (exit 1, `TimeoutError`). The sandbox
  where this ran blocks UDP sockets, including loopback sends, so DDS
  discovery/transport could not be established (both Fast DDS and Cyclone DDS
  attempted). End-to-end delivery through ROS 2 topics is **not confirmed** and
  requires an environment with working DDS networking.

Logs of these runs are in `logs/`.

## Known limitations

- `Twist` carries no timestamp: the example measures local receive silence,
  not command age at the source.
- DDS buffering can deliver an old command that looks newly received.
- The 20 Hz Python timer is not a real-time deadline guarantee.
- If this process dies it stops publishing; a downstream controller needs its
  own watchdog.
- A zero `Twist` is a command request, not a verified safe state.
- Other publishers can bypass this gate unless the deployment prevents it.
- No sensor feedback, execution acknowledgement, Gazebo validation, hardware
  test, or safety certification in this example.

## License

TBD — no license selected yet.
