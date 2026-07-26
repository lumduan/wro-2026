"""The one contract every mission program is written against.

    mission code  ──imports only──►  RobotIO
                                        │
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                  SimRobotIO      Ev3RobotIO      SpikeRobotIO
                  (CPython)       (Pybricks v2)   (Pybricks v3/v4)

**This file must run on MicroPython.** The simulator is CPython 3.13; both hubs
are MicroPython, and EV3's is v2.0 from May 2020. So nothing here may use
`typing`, `dataclasses`, `abc`, `enum`, f-strings or `async` — none of which
exists on those ports. `tools/check_portability.py` enforces that on every
commit, which is what turns the project's "one file runs on both" invariant from
a claim into a tested one.

Two platforms, two Pybricks generations:

===========  ==================================  ======================
platform     toolchain                           device module
===========  ==================================  ======================
EV3          Pybricks v2.x, in the ev3dev image  ``pybricks.ev3devices``
SPIKE Prime  Pybricks v3/v4                      ``pybricks.pupdevices``
===========  ==================================  ======================

They share ``pybricks.robotics.DriveBase`` and ``pybricks.parameters.Port``, so
the two backends are siblings rather than strangers -- but no single toolchain
targets both, which is why this contract exists.

Why the surface is shaped the way it is:

* **Intent, not actuators.** ADR-022 settled the motor budget (2 drive, 0 yaw,
  2 manipulator) but deliberately did NOT choose the mechanism -- gripper, fork,
  scoop and passive geometry are all still open, gated on object mass and grip
  points. ``pick_up()`` survives that decision; ``actuator_a(position)`` would
  bake one mechanism into all twelve mission files.
* **Reflection, not colour.** S4 7.10 lists mat brightness varying table to
  table and lighting varying hour to hour; 9.3 puts calibration in practice time
  and requires it to survive quarantine; 5.2.7 prohibits cameras, so there is no
  fallback. Colour discrimination must therefore be **ratiometric** -- a
  comparison, never an absolute threshold. Pybricks offers a convenient
  ``ColorSensor.color()`` that classifies to seven fixed colours; this contract
  does not expose it, because it is exactly the absolute test the rules warn
  against.
* **One button.** S4 5.2.6 requires a single button that both starts and stops,
  on the outer surface and not underneath.
"""

#: Units are millimetres and degrees throughout (CLAUDE.md 5.2). Headings are
#: CCW-positive with 0 degrees along +X, matching the MAT frame, so a mission's
#: turn arithmetic reads the same as the field spec's.
MM = "mm"
DEG = "deg"


class RobotIO(object):
    """What a robot must be able to do. Backends implement it; missions use it.

    Deliberately a plain class rather than an ``abc.ABC``: MicroPython has no
    ``abc``. Unimplemented methods raise, which gives the same protection at the
    only moment that matters -- when a backend forgets one.
    """

    # ------------------------------------------------------------------ #
    # Run control
    # ------------------------------------------------------------------ #

    def wait_for_start(self):
        """Block until the single start/stop button is pressed. S4 5.2.6.

        The same button ends the run, so a backend must not consume the press
        that a later ``stop()`` needs.
        """
        raise NotImplementedError("wait_for_start")

    def stop(self):
        """Halt all motion. Safe to call more than once."""
        raise NotImplementedError("stop")

    # ------------------------------------------------------------------ #
    # Motion — a differential drive, 2 of the 4 motors (ADR-022)
    # ------------------------------------------------------------------ #

    def drive_straight(self, distance_mm):
        """Drive forward ``distance_mm``; negative reverses.

        Returns when the move is complete. Blocking rather than asynchronous
        because MicroPython on these ports has no ``async``.
        """
        raise NotImplementedError("drive_straight")

    def turn(self, angle_deg):
        """Turn in place by ``angle_deg``, **CCW positive** (CLAUDE.md 5.2).

        Yaw comes from the drivetrain, not a dedicated actuator: ADR-022
        measured the tightest yaw tolerance in the game at +/-31 degrees, on the
        cables, and every other object is indifferent to heading entirely.
        """
        raise NotImplementedError("turn")

    def heading(self):
        """Best estimate of heading in degrees, CCW positive.

        An **estimate**, not truth. On hardware this is odometry and it drifts;
        field test P3 measures how much. Mission code must not assume it is
        exact, and must never use it as a substitute for a sensor reading.
        """
        raise NotImplementedError("heading")

    # ------------------------------------------------------------------ #
    # Manipulation — intent, not mechanism (ADR-022)
    # ------------------------------------------------------------------ #

    def pick_up(self):
        """Acquire the object the robot is positioned at.

        What physically happens is the backend's business. ADR-022 left the
        mechanism open on purpose; this method is the reason that decision can
        stay open without blocking mission code.
        """
        raise NotImplementedError("pick_up")

    def place(self):
        """Release the carried object where the robot is positioned.

        S6 2026-06-30 (A5) makes this the correct action when the clock is about
        to expire: an object left in the target area scores the partial tier,
        where one still held scores the same but one carried away scores zero.
        """
        raise NotImplementedError("place")

    def carrying(self):
        """True while an object is held."""
        raise NotImplementedError("carrying")

    # ------------------------------------------------------------------ #
    # Sensing — ratiometric only (S4 7.10, 9.3; cameras prohibited by 5.2.7)
    # ------------------------------------------------------------------ #

    def read_reflection(self):
        """Reflected light, 0 (none) to 100 (maximum), as a number.

        A scalar on purpose. Compare two readings, or a reading against one
        taken during practice time -- never against a constant baked into the
        program. Mat brightness varies table to table and lighting varies hour
        to hour (S4 7.10), and 9.3 forbids recalibrating after quarantine.
        """
        raise NotImplementedError("read_reflection")


class NotOnThisPlatform(Exception):
    """Raised when a hardware backend is imported somewhere it cannot run.

    Failing at import is the point: a backend that silently half-works on the
    wrong platform would be discovered on the competition table.
    """
    pass
