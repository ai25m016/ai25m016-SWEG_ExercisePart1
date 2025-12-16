import os
import sys
import subprocess

def run(cmd, env=None):
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"  # local|docker

    env = os.environ.copy()
    env.setdefault("BACKEND_BASE_URL", "http://127.0.0.1:8000")

    if mode == "docker":
        env["CHECK_FS"] = "0"
        env.setdefault("IMAGES_DIR", "backend/images")
    else:
        env.setdefault("CHECK_FS", "1")
        env.setdefault("IMAGES_DIR", "backend/images")

    run([sys.executable, "backend/tests/test_resizer.py"], env=env)

if __name__ == "__main__":
    main()
