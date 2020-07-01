#!/usr/bin/env python
import time

import pytest
import rospy
from geometry_msgs.msg import TwistStamped

from control_msgs.msg import JointJog
from trajectory_msgs.msg import JointTrajectory

# Import common Python test utilities
from os import sys, path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
import util

# Test that the servo node publishes controller commands when it receives Cartesian or joint commands.
# This can be run as part of a pytest, or like a normal ROS executable:
# rosrun moveit_servo test_servo_integration.py

JOINT_COMMAND_TOPIC = 'servo_server/delta_joint_cmds'
CARTESIAN_COMMAND_TOPIC = 'servo_server/delta_twist_cmds'

COMMAND_OUT_TOPIC = 'servo_server/command'


@pytest.fixture
def node():
    return rospy.init_node('pytest', anonymous=True)


class JointCmd(object):
    def __init__(self):
        self._pub = rospy.Publisher(JOINT_COMMAND_TOPIC, JointJog, queue_size=10)

    def send_joint_velocity_cmd(self, joint_pos):
        jj = JointJog()
        jj.header.stamp = rospy.Time.now()
        jj.joint_names = ['joint_{}'.format(i) for i in range(len(joint_pos))]
        jj.velocities = list(map(float, joint_pos))
        self._pub.publish(jj)


class CartesianCmd(object):
    def __init__(self):
        self._pub = rospy.Publisher(
            CARTESIAN_COMMAND_TOPIC, TwistStamped, queue_size=10
        )

    def send_cmd(self, linear, angular):
        ts = TwistStamped()
        ts.header.stamp = rospy.Time.now()
        ts.twist.linear.x, ts.twist.linear.y, ts.twist.linear.z = linear
        ts.twist.angular.x, ts.twist.angular.y, ts.twist.angular.z = angular
        self._pub.publish(ts)


def test_servo_cartesian_command(node):
    # Test sending a cartesian velocity command

    assert util.wait_for_servo_initialization()

    received = []
    sub = rospy.Subscriber(
        COMMAND_OUT_TOPIC, JointTrajectory, lambda msg: received.append(msg)
    )
    cartesian_cmd = CartesianCmd()

    # Repeated zero-commands should produce no output, other than a few halt messages
    # A subscriber in a different timer fills 'received'
    for i in range(4):
        cartesian_cmd.send_cmd([0, 0, 0], [0, 0, 0])
        rospy.sleep(0.1)
    received = []
    rospy.sleep(1)
    assert len(received) <= 4 # 'num_outgoing_halt_msgs_to_publish' in the config file

    # This nonzero command should produce servoing output
    # A subscriber in a different timer fills `received`
    TEST_DURATION = 1
    PUBLISH_PERIOD = 0.01 # 'PUBLISH_PERIOD' from servo config file

    # Send a command to start the servo node
    cartesian_cmd.send_cmd([0, 0, 0], [0, 0, 1])

    start_time = rospy.get_rostime()
    received = []
    while (rospy.get_rostime() - start_time).to_sec() < TEST_DURATION:
        cartesian_cmd.send_cmd([0, 0, 0], [0, 0, 1])
        time.sleep(0.1)
    # TEST_DURATION/PUBLISH_PERIOD is the expected number of messages in this duration.
    # Allow a small +/- window due to rounding/timing errors
    assert len(received) >= TEST_DURATION/PUBLISH_PERIOD - 20
    assert len(received) <= TEST_DURATION/PUBLISH_PERIOD + 20


def test_servo_joint_command(node):
    # Test sending a joint command

    assert util.wait_for_servo_initialization()

    received = []
    sub = rospy.Subscriber(
        COMMAND_OUT_TOPIC, JointTrajectory, lambda msg: received.append(msg)
    )
    joint_cmd = JointCmd()

    TEST_DURATION = 1
    PUBLISH_PERIOD = 0.01 # 'PUBLISH_PERIOD' from servo config file
    velocities = [0.1]

    # Send a command to start the servo node
    joint_cmd.send_joint_velocity_cmd(velocities)

    start_time = rospy.get_rostime()
    received = []
    while (rospy.get_rostime() - start_time).to_sec() < TEST_DURATION:
        joint_cmd.send_joint_velocity_cmd(velocities)
        time.sleep(0.1)
    # TEST_DURATION/PUBLISH_PERIOD is the expected number of messages in this duration.
    # Allow a small +/- window due to rounding/timing errors
    assert len(received) >= TEST_DURATION/PUBLISH_PERIOD - 20
    assert len(received) <= TEST_DURATION/PUBLISH_PERIOD + 20


if __name__ == '__main__':
    node = node()
    time.sleep(SERVO_SETTLE_TIME_S)  # wait for servo server to init
    test_servo_cartesian_command(node)
    test_servo_joint_command(node)
