"""Phase 6 — scoring simulation over the frozen field, scoring and object specs.

The dynamics half of Phase 6 (friction, odometry drift, sensor response) is
deliberately absent: every parameter it needs is an unmeasured ``ASSUME:`` until
field tests P1-P6 run, so a time-stepped robot model would produce numbers that
look authoritative and are not. See ``docs/FIELD_TEST_PLAN.md``.
"""
