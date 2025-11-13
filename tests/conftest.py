# tests/conftest.py
import sys, pathlib
# .../simple_social/src auf den Pythonpfad setzen
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
