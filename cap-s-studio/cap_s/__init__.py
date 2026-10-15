"""CAP-S mean curves and SD/SEM error bands."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "cap_s_matplotlib"),
)
