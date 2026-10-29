"""Fail CI unless the embedded runtime answers a snapshot on an iOS simulator."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    devices = json.loads(run('xcrun', 'simctl', 'list', 'devices', 'available', '-j'))['devices']
    iphone = next(device for runtime, entries in devices.items() if 'iOS' in runtime
                  for device in entries if device['name'].startswith('iPhone'))
    udid = iphone['udid']
    if iphone['state'] != 'Booted':
        run('xcrun', 'simctl', 'boot', udid)
    run('xcrun', 'simctl', 'bootstatus', udid, '-b')
    app = ROOT/'build/simulator/Build/Products/Debug-iphonesimulator/NYXOR.app'
    run('xcrun', 'simctl', 'install', udid, str(app))
    run('xcrun', 'simctl', 'launch', udid, 'com.thunderboldx.nyxor')
    data = Path(run('xcrun', 'simctl', 'get_app_container', udid, 'com.thunderboldx.nyxor', 'data'))
    ready = data/'Library/Application Support/NYXOR/ios-ready.json'
    deadline = time.monotonic()+60
    while time.monotonic() < deadline and not ready.exists():
        time.sleep(1)
    run('xcrun', 'simctl', 'io', udid, 'screenshot', str(ROOT/'build/ios-smoke.png'))
    if not ready.exists() or not json.loads(ready.read_text()).get('ok'):
        raise SystemExit('Embedded Python did not answer its initial snapshot. Inspect simulator logs and screenshot.')
    print('iOS simulator answered snapshot successfully. Live Twitch farming still requires device testing.')


if __name__ == '__main__':
    main()
