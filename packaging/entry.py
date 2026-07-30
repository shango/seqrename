"""PyInstaller entry point.

The frozen bundle runs this file as a top-level script, so it cannot use the
package-relative imports that ``python -m seqrename.gui`` relies on.
"""

import sys

from seqrename.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
