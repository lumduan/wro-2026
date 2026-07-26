"""EV3 backend — Pybricks v2.x on ev3dev. **UNVERIFIED against hardware.**

Every method below records the exact Pybricks call it will make and where that
call is documented. Nothing here has been executed: the team does not yet hold
the sets, and this file exists so that the scarce hardware window is spent
measuring rather than writing code. Verification is then a checklist.

Sources, read 2026-07-27:

* ``https://pybricks.com/ev3-micropython/`` — EV3 MicroPython v2.0, 18 May 2020
* ``https://docs.pybricks.com/en/v2.0/ev3devices.html`` — ``Motor(port, ...)``,
  ``ColorSensor(port)``, ``ColorSensor.reflection()`` returning 0-100
* ``https://docs.pybricks.com/en/v2.0/start_ev3.html`` — ``EV3Brick()``, and
  ``print`` built in from v2.0

**Language constraint.** EV3 MicroPython v2.0 predates MicroPython 1.17
(September 2021), which is the release that added f-strings. So this file, the
contract and every mission must avoid them. That is not a style preference; it
is a syntax error on the target.
"""

from robot_io import NotOnThisPlatform, RobotIO

#: Set once the calls below have actually been run on an EV3. Until then every
#: method raises, because a backend that returns plausible values without having
#: been tested is worse than one that refuses.
VERIFIED_ON_HARDWARE = False

UNVERIFIED = (
    "EV3 backend is UNVERIFIED against hardware. Set VERIFIED_ON_HARDWARE "
    "once field tests P1 and P3 have run. See docs/FIELD_TEST_PLAN.md.")


class Ev3RobotIO(RobotIO):
    """Pybricks v2.x implementation.

    Construction is deliberately separate from the calls: importing this module
    off-platform raises, so a mission file must not import it at module scope.
    """

    def __init__(self, left_port, right_port, sensor_port, wheel_mm, axle_mm):
        try:
            import pybricks.ev3devices          # noqa: F401
        except ImportError:
            raise NotOnThisPlatform(
                "pybricks.ev3devices is absent - this backend runs only on an "
                "EV3 running the ev3dev image with Pybricks v2.x")
        self._left_port = left_port
        self._right_port = right_port
        self._sensor_port = sensor_port
        self._wheel_mm = wheel_mm
        self._axle_mm = axle_mm
        # Planned, from docs.pybricks.com/en/v2.0/:
        #   from pybricks.hubs import EV3Brick
        #   from pybricks.ev3devices import Motor, ColorSensor
        #   from pybricks.robotics import DriveBase
        #   self._brick = EV3Brick()
        #   self._drive = DriveBase(Motor(left_port), Motor(right_port),
        #                           wheel_diameter=wheel_mm, axle_track=axle_mm)
        #   self._sensor = ColorSensor(sensor_port)
        raise NotImplementedError(UNVERIFIED)

    def wait_for_start(self):
        # EV3Brick().buttons.pressed() polled until non-empty.
        # docs.pybricks.com/en/v2.0/hubs.html  ·  S4 5.2.6 one button
        raise NotImplementedError(UNVERIFIED)

    def stop(self):
        # DriveBase.stop()
        # docs.pybricks.com/en/v2.0/robotics.html
        raise NotImplementedError(UNVERIFIED)

    def drive_straight(self, distance_mm):
        # DriveBase.straight(distance_mm) - blocking, millimetres
        # docs.pybricks.com/en/v2.0/robotics.html
        raise NotImplementedError(UNVERIFIED)

    def turn(self, angle_deg):
        # DriveBase.turn(angle_deg). NOTE: Pybricks turn() is CLOCKWISE
        # positive; the contract is CCW positive (CLAUDE.md 5.2), so this
        # backend must negate. Getting that wrong mirrors every mission.
        # docs.pybricks.com/en/v2.0/robotics.html
        raise NotImplementedError(UNVERIFIED)

    def heading(self):
        # DriveBase.angle(), negated for the CCW convention. Odometry only -
        # the EV3 has no gyro in the base set. Field test P3 measures drift.
        raise NotImplementedError(UNVERIFIED)

    def pick_up(self):
        # Mechanism undecided (ADR-022, gated on mass and grip points from
        # field test P7). Will drive one of the two free motors.
        raise NotImplementedError(UNVERIFIED)

    def place(self):
        # The reverse of pick_up on whichever mechanism ADR-022 settles on.
        # S6 2026-06-30 (A5) makes releasing before the clock expires the
        # correct action: an object left in the area scores the partial tier.
        raise NotImplementedError(UNVERIFIED)

    def carrying(self):
        # Tracked in software; no sensor is budgeted for it (ADR-022 leaves
        # exactly 2 motor slots and no spare port is assumed).
        raise NotImplementedError(UNVERIFIED)

    def read_reflection(self):
        # ColorSensor.reflection() -> 0..100
        # docs.pybricks.com/en/v2.0/ev3devices.html
        # NOT ColorSensor.color(): that classifies to seven fixed colours on an
        # absolute threshold, which S4 7.10 and 9.3 argue against.
        raise NotImplementedError(UNVERIFIED)
