"""Run against a real ROS 2 installation; no mocks or hardware."""
import os
import pathlib
import subprocess
import sys
import time


def main():
    import rclpy
    from geometry_msgs.msg import Twist

    rclpy.init()
    node = rclpy.create_node('ethosguard_transport_test')
    received = []
    sub = node.create_subscription(
        Twist, '/ethosguard_demo/checked',
        lambda msg: received.append((msg.linear.x, msg.linear.y, msg.linear.z,
                                     msg.angular.x, msg.angular.y, msg.angular.z)), 10)
    pub = node.create_publisher(Twist, '/ethosguard_demo/raw', 1)
    path = pathlib.Path(__file__).with_name('ethosguard_ros2_mre.py')
    log = open('ros_node.log', 'w')
    process = subprocess.Popen([sys.executable, '-u', str(path)], stdout=log,
                               stderr=subprocess.STDOUT)
    zero = (0.0,) * 6

    def wait_for(predicate, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Demo exited; inspect ros_node.log')
            rclpy.spin_once(node, timeout_sec=0.02)
            if predicate():
                return
        raise TimeoutError('ROS transport expectation timed out')

    def send_for(value, duration=1.0):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            msg = Twist()
            msg.linear.x = value
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.05)

    try:
        wait_for(lambda: pub.get_subscription_count() > 0 and bool(received))
        assert received[-1] == zero
        print('PASS: startup output is zero', flush=True)
        received.clear()
        send_for(0.2)
        assert (0.2,) + zero[1:] in received
        print('PASS: valid command crossed ROS topics', flush=True)
        received.clear()
        wait_for(lambda: bool(received) and received[-1] == zero)
        print('PASS: silence timeout produced zero', flush=True)
        send_for(0.6)
        received.clear()
        send_for(0.2)
        assert received and all(v == zero for v in received)
        log.flush()
        text = pathlib.Path('ros_node.log').read_text()
        assert 'DEGRADED' in text and 'FAIL_SAFE' in text
        print('PASS: invalid-command escalation and latch across ROS topics', flush=True)
        print('ROS_TRANSPORT_PASS', flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
