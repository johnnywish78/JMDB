#!/usr/bin/env python3
import argparse, os, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
ELECTRON = ROOT / "electron"

def validate_python():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(f"ERROR: Python 3.10+ required, found {sys.version}")
        sys.exit(1)
    print(f"[JMDB] Python {sys.version.split()[0]}")

def validate_deps():
    required = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "httpx", "psutil"]
    missing = [d for d in required if not __import__(d, fromlist=[''])]
    if missing:
        print(f"ERROR: Missing: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    print("[JMDB] Dependencies OK")

def start_backend(host, port, log_level):
    env = os.environ.copy()
    env["JMDB_BACKEND_PORT"] = str(port)
    env["JMDB_DATA_DIR"] = str(ROOT / "data")
    print(f"[JMDB] Starting backend on {host}:{port}")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port), "--log-level", log_level],
        cwd=str(ROOT), env=env
    )

def wait_backend(host, port, timeout=30):
    url = f"http://{host}:{port}/api/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            if urllib.request.urlopen(url, timeout=2).getcode() == 200:
                print("[JMDB] Backend healthy")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("[JMDB] ERROR: Backend failed")
    return False

def start_electron(port):
    electron_bin = ELECTRON / "node_modules" / ".bin" / "electron"
    if not electron_bin.exists():
        print("[JMDB] WARNING: Electron not installed")
        return None
    
    env = os.environ.copy()
    env["JMDB_BACKEND_PORT"] = str(port)
    print("[JMDB] Starting Electron...")
    return subprocess.Popen(
        [str(electron_bin), str(ELECTRON), "--no-sandbox"],
        cwd=str(ELECTRON), env=env
    )

def cleanup(bp, ep):
    print("[JMDB] Shutting down...")
    if ep:
        try: ep.terminate(); ep.wait(timeout=5)
        except: ep.kill()
    if bp:
        try: bp.terminate(); bp.wait(timeout=5)
        except: bp.kill()
    print("[JMDB] Done")

def main():
    parser = argparse.ArgumentParser(description="JMDB")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--no-electron", action="store_true")
    args = parser.parse_args()
    
    print("="*60)
    print("  JMDB - Johnny's Media Database v1.0.0")
    print("="*60)
    
    validate_python()
    validate_deps()
    
    bp = start_backend(args.host, args.port, args.log_level)
    if not wait_backend(args.host, args.port):
        bp.kill()
        sys.exit(1)
    
    if args.no_electron:
        print("[JMDB] Backend only. Press Ctrl+C to stop.")
        try:
            bp.wait()
        except KeyboardInterrupt:
            cleanup(bp, None)
        return
    
    ep = start_electron(args.port)
    
    def sig(s, f):
        cleanup(bp, ep)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, sig)
    signal.signal(signal.SIGTERM, sig)
    
    try:
        if ep:
            ep.wait()
        else:
            bp.wait()
    except:
        pass
    finally:
        cleanup(bp, ep)

if __name__ == "__main__":
    main()
