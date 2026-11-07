import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("MESHAUDIT_PROVEEDOR", "falso")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
