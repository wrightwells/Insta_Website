"""Replace the approved Box Storage route with private MySite at the host root."""
import argparse
import copy
import json
import subprocess
import tempfile

HOST = 'dell-linux-mint.bandicoot-pumpkinseed.ts.net'
TARGET = 'http://127.0.0.1:8002'
OLD_ROOT = {'Proxy': 'http://127.0.0.1:8080'}
OLD_PATH = {'Proxy': 'http://127.0.0.1:8002/mysite'}


def read_config():
    return json.loads(subprocess.run(
        ['tailscale', 'serve', 'status', '--json'],
        check=True, capture_output=True, text=True,
    ).stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Snapshot and apply the owner-approved root replacement.')
    args = parser.parse_args()
    before = read_config()
    state = json.loads(subprocess.run(
        ['tailscale', 'status', '--json'], check=True, capture_output=True, text=True,
    ).stdout)
    if state.get('Self', {}).get('DNSName', '').rstrip('.') != HOST:
        raise SystemExit('This is not the approved Tailscale node. No changes made.')
    if any(before.get('AllowFunnel', {}).values()):
        raise SystemExit('Funnel is enabled. Inspect public exposure before proceeding. No changes made.')
    host_key = HOST + ':443'
    handlers = before.get('Web', {}).get(host_key, {}).get('Handlers', {})
    if handlers.get('/') not in (OLD_ROOT, {'Proxy': TARGET}):
        raise SystemExit('Unexpected root handler. No changes made.')
    legacy_paths = [path for path in handlers if path.rstrip('/') == '/mysite']
    if any(handlers[path] != OLD_PATH for path in legacy_paths):
        raise SystemExit('Unexpected legacy MySite handler. No changes made.')
    expected = copy.deepcopy(before)
    expected_handlers = expected['Web'][host_key]['Handlers']
    expected_handlers['/'] = {'Proxy': TARGET}
    for path in legacy_paths:
        del expected_handlers[path]
    if not args.apply:
        print(f'Plan: https://{HOST}/ -> {TARGET}; remove legacy /mysite/ handler and Box Storage route; tailnet only. Other routes preserved.')
        return
    with tempfile.NamedTemporaryFile(mode='w', prefix='insta-root-serve-before-', suffix='.json', delete=False) as handle:
        json.dump(before, handle, indent=2)
        snapshot = handle.name
    print('Pre-change snapshot: ' + snapshot, flush=True)
    commands = [['tailscale', 'serve', '--bg', '--yes', '--https=443', '--set-path=/', TARGET]]
    commands.extend(['tailscale', 'serve', '--bg', '--yes', '--https=443', '--set-path=' + path, 'off'] for path in legacy_paths)
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit('Serve update failed; inspect current state and snapshot ' + snapshot + ': ' + (result.stderr.strip() or result.stdout.strip()))
    if read_config() != expected:
        raise SystemExit('Unexpected Serve configuration; inspect current state and snapshot ' + snapshot)
    print(f'Configured https://{HOST}/ (tailnet only). Box Storage route removed. Other Serve settings unchanged.')


if __name__ == '__main__':
    main()
