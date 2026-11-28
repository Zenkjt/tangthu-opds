#!/usr/bin/env python3
"""Snapshot and acknowledge the Apps Script's accumulated partial-build queue."""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

QUEUE_FILE = Path('.build/partial_build_queue.json')
SNAPSHOT_FILE = Path('.build/partial_build_snapshot.json')
ACK_RETRY_INTERVAL_SECONDS = 30
ACK_RETRY_TIMEOUT_SECONDS = 30 * 60


def post(action: str, payload: dict) -> dict:
    url = os.environ.get('TANGTHU_APPS_SCRIPT_URL', '').strip()
    token = os.environ.get('TANGTHU_BUILD_SYNC_TOKEN', '').strip()
    if not url or not token:
        raise RuntimeError('Missing TANGTHU_APPS_SCRIPT_URL or TANGTHU_BUILD_SYNC_TOKEN.')
    body = json.dumps({'action': action, 'token': token, **payload}).encode()
    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode('utf-8'))
    if not result.get('ok'):
        raise RuntimeError(f'Apps Script {action} failed: {result}')
    return result


def post_ack_with_lock_retry(payload: dict) -> dict:
    """Retry ACK only when Apps Script reports contention on its script lock."""
    deadline = time.monotonic() + ACK_RETRY_TIMEOUT_SECONDS
    attempt = 0

    while True:
        attempt += 1
        try:
            return post('partial_build_queue_ack', payload)
        except RuntimeError as error:
            message = str(error)
            if 'lock timeout' not in message.lower():
                raise

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    'Apps Script ACK kept encountering Lock timeout for '
                    f'{ACK_RETRY_TIMEOUT_SECONDS // 60} minutes; queue retained. Last error: {message}'
                ) from error

            delay = min(ACK_RETRY_INTERVAL_SECONDS, remaining)
            print(
                f'ACK waiting for Apps Script lock (attempt {attempt}); '
                f'retrying in {int(delay)}s, '
                f'{int(remaining // 60)}m remaining.',
                flush=True,
            )
            time.sleep(delay)


def snapshot() -> None:
    result = post('partial_build_queue_get', {})
    rows = result.get('snapshot', [])
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(rows, ensure_ascii=False, indent=2) + '\n'
    QUEUE_FILE.write_text(serialized, encoding='utf-8')
    SNAPSHOT_FILE.write_text(serialized, encoding='utf-8')
    print(f"Partial queue snapshot: {len(rows)} shelf(s)")
    for row in rows:
        print(f" - {row.get('shelf_id')} v{row.get('version')}")


def validate_shelves(ids: list[str]) -> None:
    """Validate requested shelf IDs against the current catalog/lifecycle state."""
    required = [Path('docs/catalog.json'), Path('config/branches.json'), Path('.build/lifecycle.json'), Path('.build/branches.json')]
    if not all(path.exists() for path in required):
        raise RuntimeError('Required catalog/lifecycle state missing; queue retained. Run Full Build first.')

    catalog = json.loads(required[0].read_text(encoding='utf-8'))
    config = json.loads(required[1].read_text(encoding='utf-8'))
    lifecycle = json.loads(required[2].read_text(encoding='utf-8'))
    active = json.loads(required[3].read_text(encoding='utf-8'))
    catalog_rows = catalog.get('branches', [])
    catalog_ids = {str(row.get('id')) for row in catalog_rows if row.get('id')}
    config_rows = config.get('branches', [])
    config_ids = {str(row.get('id')) for row in config_rows if row.get('id')}
    active_ids = {str(row.get('id')) for row in active.get('branches', []) if row.get('id')}
    stats_ok = catalog.get('version') == 2 and bool(catalog_rows) and all(
        isinstance(row.get('book_count'), int)
        and isinstance(row.get('font_count'), int)
        and isinstance(row.get('format_counts'), dict)
        for row in catalog_rows
    )
    by_id = {str(row.get('id')): row for row in catalog_rows}
    lifecycle_changed = any(
        by_id.get(str(row.get('id')), {}).get('status', 'active') != row.get('status', 'active')
        for row in lifecycle.get('branches', [])
    )

    def clean_name(row):
        return str(row.get('name') or row.get('display_name') or '').removeprefix('[SUSPENDED] ')

    names_changed = any(
        clean_name(by_id.get(str(row.get('id')), {})) != row.get('display_name')
        or by_id.get(str(row.get('id')), {}).get('root_folder_id') != row.get('root_folder_id')
        for row in config_rows
    )
    if not (stats_ok and catalog_ids == config_ids and not lifecycle_changed and not names_changed and all(i in active_ids for i in ids)):
        raise RuntimeError('Partial build safety check failed; queue retained. Full Build is required before Partial Build.')


def write_resolution(ids: list[str], reason: str) -> None:
    Path('.build/build_mode').write_text('incremental\n', encoding='utf-8')
    Path('.build/changed_shelves.txt').write_text(','.join(ids) + '\n', encoding='utf-8')
    print(f'Build mode: incremental ({reason})')


def resolve() -> None:
    rows = json.loads(QUEUE_FILE.read_text(encoding='utf-8')) if QUEUE_FILE.exists() else []
    ids = list(dict.fromkeys(str(row.get('shelf_id', '')).strip() for row in rows if row.get('shelf_id')))
    if not ids:
        Path('.build/build_mode').write_text('skip\n', encoding='utf-8')
        Path('.build/changed_shelves.txt').write_text('\n', encoding='utf-8')
        print('Build mode: skip (no pending changed shelves)')
        return
    validate_shelves(ids)
    write_resolution(ids, 'validated accumulated changed-shelf queue')


def resolve_single(shelf_id: str) -> None:
    shelf_id = str(shelf_id or '').strip()
    if not shelf_id:
        raise RuntimeError('Single-shelf build requires a non-empty branch_id.')
    validate_shelves([shelf_id])
    write_resolution([shelf_id], f'validated isolated Refresh for {shelf_id}')


def ack() -> None:
    rows = json.loads(SNAPSHOT_FILE.read_text(encoding='utf-8')) if SNAPSHOT_FILE.exists() else []
    result = post_ack_with_lock_retry({'snapshot': rows})
    print(f"Partial queue ACK: cleared={len(result.get('cleared', []))}, remaining={result.get('remaining')}")


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'snapshot':
        snapshot()
    elif command == 'resolve':
        resolve()
    elif command == 'resolve-single' and len(sys.argv) == 3:
        resolve_single(sys.argv[2])
    elif command == 'ack':
        ack()
    else:
        raise SystemExit('Usage: partial_build_queue.py snapshot|resolve|resolve-single <branch_id>|ack')
