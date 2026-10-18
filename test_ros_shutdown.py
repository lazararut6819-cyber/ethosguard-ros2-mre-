"""Real ROS smoke test: timer startup, then SIGTERM without traceback."""
import pathlib
import subprocess
import sys
import time

log_path = pathlib.Path('ros_shutdown_test.log')
with log_path.open('w') as log:
    process = subprocess.Popen(
        [sys.executable, '-u', str(pathlib.Path(__file__).with_name('ethosguard_ros2_mre.py'))],
        stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 10
        while 'STALE' not in log_path.read_text():
            if process.poll() is not None:
                raise RuntimeError('Node exited before STALE; inspect log')
            if time.monotonic() > deadline:
                raise TimeoutError('No STALE timer callback; inspect log')
            time.sleep(0.1)
        process.terminate()
        code = process.wait(timeout=5)
        assert code == 0, f'Node exit code: {code}'
        assert 'Traceback' not in log_path.read_text()
        print('ROS_SHUTDOWN_PASS: STALE observed, SIGTERM exit 0, no traceback')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
