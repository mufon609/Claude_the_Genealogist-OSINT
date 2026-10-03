"""The interpreter's startup hook: puts the check's network guard (tests/checks/offline.py) on every Python process a check starts."""
import offline
offline.install()
