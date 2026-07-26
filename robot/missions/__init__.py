"""Mission programs, written against `robot_io.RobotIO` and nothing else.

This file exists so `missions` imports as a package under pytest. A hub does not
need it: hub files are copied flat, which is also why
`tools/check_portability.py` rejects relative imports.
"""
