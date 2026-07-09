import runpy
import sys
from pathlib import Path

scripts_dir = Path(__file__).with_name("scripts")
sys.path.insert(0, str(scripts_dir))
if len(sys.argv) == 1:
    sys.argv.extend(["test_images/test_1.png", "test_images/test_2.png"])
runpy.run_path(str(scripts_dir / "manual_test_compare_images.py"), run_name="__main__")
