import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT    = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_UVICORN = BACKEND / "venv" / "Scripts" / "uvicorn.exe"

env = os.environ.copy()
env["PYTHONPATH"] = str(BACKEND)

print("Starting Care Intelligence...")
print()

# ── Backend ────────────────────────────────────────────────────────────────
backend = subprocess.Popen(
    [str(VENV_UVICORN), "app.main:app", "--reload", "--port", "8000"],
    cwd=str(BACKEND),
    env=env,
)
print("✓ Backend starting on http://localhost:8000")

# ── Frontend ───────────────────────────────────────────────────────────────
npm = "npm.cmd" if sys.platform == "win32" else "npm"
frontend = subprocess.Popen(
    [npm, "run", "dev"],
    cwd=str(FRONTEND),
)
print("✓ Frontend starting on http://localhost:5173")
print()

# Wait for frontend to be ready then open browser
time.sleep(4)
webbrowser.open("http://localhost:5173")
print("✓ Opened http://localhost:5173 in browser")
print()
print("Press Ctrl+C to stop both servers.")

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    backend.terminate()
    frontend.terminate()
    backend.wait()
    frontend.wait()
    print("Done.")
