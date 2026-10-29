"""Fail CI unless the embedded runtime answers a snapshot on an iOS simulator."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def run(*args, timeout=120):
    print('RUN', *args, flush=True)
    result = subprocess.check_output(args, text=True, timeout=timeout).strip()
    if result: print(result[:2000], flush=True)
    return result


def main():
    devices = json.loads(run('xcrun', 'simctl', 'list', 'devices', 'available', '-j'))['devices']
    iphone = next(device for runtime, entries in devices.items() if 'iOS' in runtime
                  for device in entries if device['name'].startswith('iPhone'))
    udid = iphone['udid']
    if iphone['state'] != 'Booted':
        run('xcrun', 'simctl', 'boot', udid)
    run('xcrun', 'simctl', 'bootstatus', udid, '-b', timeout=420)
    app = ROOT/'build/simulator/Build/Products/Debug-iphonesimulator/NYXOR.app'
    run('xcrun', 'simctl', 'install', udid, str(app))
    run('xcrun', 'simctl', 'launch', '--stdout='+str(ROOT/'build/ios-stdout.log'),
        '--stderr='+str(ROOT/'build/ios-stderr.log'), udid, 'com.thunderboldx.nyxor')
    data = Path(run('xcrun', 'simctl', 'get_app_container', udid, 'com.thunderboldx.nyxor', 'data'))
    ready = data/'Library/Application Support/NYXOR/ios-ready.json'
    deadline = time.monotonic()+60
    while time.monotonic() < deadline and not ready.exists():
        time.sleep(1)
    run('xcrun', 'simctl', 'io', udid, 'screenshot', str(ROOT/'build/ios-smoke.png'))
    if not ready.exists() or not json.loads(ready.read_text()).get('ok'):
        for name in ('ios-stdout.log', 'ios-stderr.log'):
            path = ROOT/'build'/name
            if path.exists(): print(name, path.read_text(errors='replace')[-16000:], flush=True)
        try:
            logs = run('xcrun', 'simctl', 'spawn', udid, 'log', 'show', '--last', '3m',
                       '--style', 'compact', '--predicate', 'process == "NYXOR"', timeout=60)
            (ROOT/'build/ios-runtime.log').write_text(logs)
        except (subprocess.SubprocessError, OSError) as error:
            print('Runtime log collection:', type(error).__name__, flush=True)
        raise SystemExit('Embedded Python did not answer its initial snapshot. Inspect simulator logs and screenshot.')
    print('iOS simulator answered snapshot successfully. Live Twitch farming still requires device testing.')


if __name__ == '__main__':
    main()
