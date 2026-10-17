"""Entry point of the installed NEXVARA.exe (PyInstaller)."""

import sys

from nexvara.app.main import main

if __name__ == "__main__":
    sys.exit(main())
