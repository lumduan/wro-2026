"""SPIKE Prime backend — Pybricks v3/v4. **UNVERIFIED against hardware.**

Sibling of ``robot_io_ev3.py``, and the differences are the point: the two hubs
run the same Pybricks family at two generations, so the API shapes match but the
device module does not.

============  ==============================  =========================
              EV3                             SPIKE Prime
============  ==============================  =========================
toolchain     Pybricks v2.x (ev3dev image)    Pybricks v3/v4
devices       ``pybricks.ev3devices``         ``pybricks.pupdevices``
hub class     ``EV3Brick``                    ``PrimeHub``
shared        ``pybricks.robotics.DriveBase``, ``pybricks.parameters.Port``
============  ==============================  =========================

Sources, read 2026-07-27:

* ``https://docs.pybricks.com/en/latest/pupdevices/index.html`` — ``Motor``,
  ``ColorSensor`` live in ``pybricks.pupdevices``
* ``https://github.com/pybricks/pybricks-micropython`` — v3/v4 targets the six
  modern hubs including the SPIKE Prime Hub; **EV3 is not among them**, which is
  why one toolchain cannot serve both and this contract exists

Nothing here has been executed. Every method records the call it will make so
that arriving hardware verifies a checklist rather than prompting a rewrite.
"""

from robot_io import NotOnThisPlatform, RobotIO

#: Set once these calls have actually run on a SPIKE Prime hub.
VERIFIED_ON_HARDWARE = False

UNVERIFIED = (
    "SPIKE backend is UNVERIFIED against hardware. Set VERIFIED_ON_HARDWARE "
    "once field tests P1 and P3 have run. See docs/FIELD_TEST_PLAN.md.")


class SpikeRobotIO(RobotIO):
    """Pybricks v3/v4 implementation for the SPIKE Prime hub."""

    def __init__(self, left_port, right_port, sensor_port, wheel_mm, axle_mm):
        try:
            import pybricks.pupdevices          # noqa: F401
        except ImportError:
            raise NotOnThisPlatform(
                "pybricks.pupdevices is absent - this backend runs only on a "
                "hub flashed with Pybricks v3 or v4")
        self._left_port = left_port
        self._right_port = right_port
        self._sensor_port = sensor_port
        self._wheel_mm = wheel_mm
        self._axle_mm = axle_mm
        # Planned, from docs.pybricks.com/en/latest/:
        #   from pybricks.hubs import PrimeHub
        #   from pybricks.pupdevices import Motor, ColorSensor
        #   from pybricks.robotics import DriveBase
        #   self._hub = PrimeHub()
        #   self._drive = DriveBase(Motor(left_port), Motor(right_port),
        #                           wheel_diameter=wheel_mm, axle_track=axle_mm)
        #   self._sensor = ColorSensor(sensor_port)
        raise NotImplementedError(UNVERIFIED)

    def wait_for_start(self):
        # PrimeHub().buttons.pressed() polled until non-empty.
        # docs.pybricks.com/en/latest/hubs/primehub.html  ·  S4 5.2.6
        raise NotImplementedError(UNVERIFIED)

    def stop(self):
        # DriveBase.stop()
        raise NotImplementedError(UNVERIFIED)

    def drive_straight(self, distance_mm):
        # DriveBase.straight(distance_mm) - blocking, millimetres
        # docs.pybricks.com/en/latest/robotics.html
        raise NotImplementedError(UNVERIFIED)

    def turn(self, angle_deg):
        # DriveBase.turn(angle_deg), CLOCKWISE positive in Pybricks; the
        # contract is CCW positive (CLAUDE.md 5.2), so negate here too.
        raise NotImplementedError(UNVERIFIED)

    def heading(self):
        # PrimeHub has an IMU, so heading can come from imu.heading() rather
        # than pure odometry - a real difference from the EV3 backend, and one
        # field test P3 should quantify separately per platform.
        # docs.pybricks.com/en/latest/hubs/primehub.html
        raise NotImplementedError(UNVERIFIED)

    def pick_up(self):
        # Mechanism undecided (ADR-022). One of the two free motors.
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
        # docs.pybricks.com/en/latest/pupdevices/colorsensor.html
        # NOT color(): absolute classification, which S4 7.10 / 9.3 argue
        # against. See the contract's module docstring.
        raise NotImplementedError(UNVERIFIED)
