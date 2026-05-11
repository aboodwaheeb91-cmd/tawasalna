import os
import time
import subprocess
import hashlib
import sys

WATCH_EXTENSIONS = {'.py', '.html', '.txt', '.json', '.md', '.sh', '.toml', '.cfg', '.ini', '.yaml', '.yml'}
IGNORE_DIRS = {'.git', '__pycache__', '.cache', '.pythonlibs', '.upm', '.local', 'node_modules', 'logs'}
SETTLE_SECONDS = 5
POLL_INTERVAL = 3

def get_file_snapshot(root='.'):
    snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in filenames:
            _, ext = os.path.splitext(fname)
            if ext in WATCH_EXTENSIONS:
                fpath = os.path.join(dirpath, fname)
                try:
                    stat = os.stat(fpath)
                    snapshot[fpath] = stat.st_mtime
                except OSError:
                    pass
    return snapshot

def run(cmd, **kwargs):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)

def setup_git_credentials():
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        print('[auto-sync] ERROR: GITHUB_TOKEN secret is not set. Exiting.')
        sys.exit(1)

    result = run('git remote get-url origin')
    remote_url = result.stdout.strip()

    if remote_url.startswith('https://') and '@' not in remote_url:
        repo_part = remote_url.replace('https://github.com/', '')
        new_url = f'https://x-access-token:{token}@github.com/{repo_part}'
        run(f'git remote set-url origin {new_url}')
        print('[auto-sync] Git remote configured with token.')

    run('git config user.email "auto-sync@replit.com"')
    run('git config user.name "Replit Auto-Sync"')

def push_changes():
    result_add = run('git add -A')
    if result_add.returncode != 0:
        print(f'[auto-sync] git add failed: {result_add.stderr}')
        return False

    result_status = run('git status --porcelain')
    if not result_status.stdout.strip():
        print('[auto-sync] Nothing to commit.')
        return True

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    result_commit = run(f'git commit -m "Auto-sync: {timestamp}"')
    if result_commit.returncode != 0:
        print(f'[auto-sync] git commit failed: {result_commit.stderr}')
        return False

    result_push = run('git push origin main')
    if result_push.returncode != 0:
        print(f'[auto-sync] git push failed: {result_push.stderr}')
        return False

    print(f'[auto-sync] Pushed changes at {timestamp}')
    return True

def main():
    print('[auto-sync] Starting GitHub auto-sync watcher...')
    setup_git_credentials()

    push_changes()

    snapshot = get_file_snapshot()
    last_change_time = None

    while True:
        time.sleep(POLL_INTERVAL)
        new_snapshot = get_file_snapshot()

        changed = (new_snapshot != snapshot)

        if changed:
            snapshot = new_snapshot
            last_change_time = time.time()
            print('[auto-sync] Change detected, waiting for activity to settle...')

        if last_change_time and (time.time() - last_change_time >= SETTLE_SECONDS):
            last_change_time = None
            push_changes()
            snapshot = get_file_snapshot()

if __name__ == '__main__':
    main()
