import sys
import os
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from live_paper_bot import main

if __name__ == "__main__":
    main()
