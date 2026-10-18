"""Standalone EthosGuard concept demo; no physical safety assurance."""
import math
import sys
import time


class Gate:
    def __init__(self):
        self.last_rx = None
        self.command = (0.0,) * 6
        self.faults = 0
        self.latched = False

    def receive(self, values, now):
        values = tuple(values)
        valid = (len(values) == 6 and all(math.isfinite(v) for v in values)
                 and all(abs(v) <= 0.5 for v in values[:3])
                 and all(abs(v) <= 1.0 for v in values[3:]))
        self.last_rx = now
        if not valid:
            self.faults += 1
            self.latched |= self.faults >= 2
            self.command = (0.0,) * 6
        else:
            self.faults = 0
            self.command = values

    def output(self, now):
        if self.latched:
            return 'FAIL_SAFE', (0.0,) * 6
        if self.last_rx is None or now - self.last_rx > 0.5:
            return 'STALE', (0.0,) * 6
        if self.faults:
            return 'DEGRADED', (0.0,) * 6
        return 'NOMINAL', self.command


def self_test():
    g = Gate()
    zero = (0.0,) * 6
    good = (0.2, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert g.output(0.0) == ('STALE', zero)
    g.receive(good, 1.0)
    assert g.output(1.1) == ('NOMINAL', good)
    assert g.output(1.6) == ('STALE', zero)
    g.receive((float('nan'),) + zero[1:], 2.0)
    assert g.output(2.0) == ('DEGRADED', zero)
    g.receive((0.6,) + zero[1:], 2.1)
    assert g.output(2.1) == ('FAIL_SAFE', zero)
    g.receive(good, 2.2)
    assert g.output(2.2) == ('FAIL_SAFE', zero)
    print('PASS: startup, forwarding, timeout, NaN, bounds, latch')


def run_ros():
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from geometry_msgs.msg import Twist

    class Demo(Node):
        def __init__(self):
            super().__init__('ethosguard_mre')
            self.gate = Gate()
            self.previous_mode = None
            self.pub = self.create_publisher(Twist, '/ethosguard_demo/checked', 1)
            self.sub = self.create_subscription(
                Twist, '/ethosguard_demo/raw', self.receive, 1)
            self.timer = self.create_timer(0.05, self.tick)

        def receive(self, msg):
            self.gate.receive((msg.linear.x, msg.linear.y, msg.linear.z,
                               msg.angular.x, msg.angular.y, msg.angular.z),
                              time.monotonic())

        def tick(self):
            mode, v = self.gate.output(time.monotonic())
            msg = Twist()
            msg.linear.x, msg.linear.y, msg.linear.z = v[:3]
            msg.angular.x, msg.angular.y, msg.angular.z = v[3:]
            self.pub.publish(msg)
            if mode != self.previous_mode:
                self.get_logger().info(mode)
                self.previous_mode = mode

    rclpy.init()
    node = Demo()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    self_test() if '--self-test' in sys.argv else run_ros()
