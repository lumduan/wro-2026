"""The trivial mission `docs/FIELD_TEST_PLAN.md` Step 1 asks for.

    drive 500 mm, turn 90 degrees, read a colour

Its job is not to score points. It is the smallest program that exercises every
category in the contract -- motion, rotation and sensing -- so that running it on
both hubs answers the one question Step 1 poses: does ``RobotIO`` need one
implementation or two?

**This file imports only `robot_io`.** That is the project's core invariant, and
`tools/check_portability.py` asserts it rather than trusting it.
"""

from robot_io import RobotIO


DRIVE_MM = 500
TURN_DEG = 90


def run(robot):
    """Execute the mission. Returns the reflection reading taken at the end.

    Takes the robot as an argument rather than constructing one: the same
    function then runs against the simulator in a test and against a hub
    backend on the table, which is the whole point of the contract.
    """
    robot.wait_for_start()
    robot.drive_straight(DRIVE_MM)
    robot.turn(TURN_DEG)
    reading = robot.read_reflection()
    robot.stop()
    return reading


def main():  # pragma: no cover - runs on a hub, not in CI
    """Entry point for a hub. Constructing the backend is the hub's business.

    Deliberately not written here: importing a hardware backend at module scope
    would make this file unimportable on the simulator, and the contract exists
    so that one file runs in both places.
    """
    raise NotImplementedError(
        "construct a backend and call run(robot) - see robot/robot_io_ev3.py "
        "or robot/robot_io_spike.py")
