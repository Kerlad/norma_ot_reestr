"""Single place for platform checks. Tests patch these flags, not sys.platform."""
import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
