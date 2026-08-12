"""Machine-readable JSON report — just the collected report dict, pretty-printed."""
import json
import os


def write(report, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return out_path
