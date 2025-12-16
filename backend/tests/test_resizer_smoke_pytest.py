import importlib.util
from pathlib import Path

import pytest

@pytest.mark.unit
def test_resizer_smoke_script_runs():
    # lädt backend/tests/test_resizer.py als "modul" ohne package-import
    here = Path(__file__).resolve().parent
    script = here / "test_resizer.py"

    spec = importlib.util.spec_from_file_location("resizer_smoke", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    # main() ausführen -> wenn es crasht, ist der Test rot
    mod.main()
