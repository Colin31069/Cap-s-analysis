from __future__ import annotations

from matplotlib import cm

DEFAULT_ROOT_PATH = "/Users/k/Downloads/20260303"
DEFAULT_MEDICINE_COUNT = 1
MAX_MEDICINES = 5
METADATA_FILENAME = ".skin_analysis_metadata.json"

DATA_COL = "pF - Plot 0"
DT_SEC = 0.1
INITIAL_BASELINE_POINTS = 200  # 20 seconds
DROP_SIGMA_THRESHOLD = 3.0
COLOR_PALETTE = tuple(cm.tab10.colors)
LINE_STYLE_CYCLE = ("-", "--", "-.", ":")
