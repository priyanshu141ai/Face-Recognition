import runpy
import sys
from pathlib import Path

scripts_dir = Path(__file__).with_name("scripts")
sys.path.insert(0, str(scripts_dir))
if len(sys.argv) == 1:
    sys.argv.append("test_images/priyanshu.png")
runpy.run_path(str(scripts_dir / "manual_test_single_image.py"), run_name="__main__")
