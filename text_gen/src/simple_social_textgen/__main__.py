# text_gen/src/simple_social_textgen/__main__.py
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv, find_dotenv


def main() -> None:
    """
    Ermöglicht: python -m simple_social_textgen
    Lädt .env (falls vorhanden) und startet dann die Worker-main().
    """

    # 1) Optional: .env automatisch laden (lokal hilfreich)
    # - lädt zuerst ein .env im aktuellen Ordner
    # - und/oder findet ein .env irgendwo "oben"
    # In Docker nutzt du meist env vars / env_file => schadet aber nicht.
    load_dotenv(find_dotenv(usecwd=True), override=False)

    # 2) Start der eigentlichen App
    from .main import main as worker_main  # lazy import nach env-load

    worker_main()


if __name__ == "__main__":
    main()
