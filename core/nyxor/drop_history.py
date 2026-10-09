"""Durable confirmed claims; every reward has its own stable identity."""
import json
from collections import deque
from datetime import datetime, timezone
from nyxor import paths
from nyxor.storage import load_json, atomic_write_json

MAX_DROPS = 500


def pending_claim(user_id, campaign_id, drop_id, *, add=False):
    path = paths.DATA_DIR / 'pending-claims.json'
    items = load_json(path, [])
    if not isinstance(items, list):
        items = []
    identity = f'{user_id}:{campaign_id}:{drop_id}'
    if add and identity not in items:
        atomic_write_json(path, (items + [identity])[-MAX_DROPS:])
    return identity in items


def _rows():
    result = deque(maxlen=MAX_DROPS)
    count = 0
    try:
        with paths.HISTORY_PATH.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                count += 1
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and (row.get('confirmed') or str(row.get('claim', '')).startswith('✅')):
                        result.append(row)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return []
    result = list(result)
    if count > MAX_DROPS or len(result) != count:
        _write(result)
    return result


def _write(rows):
    path = paths.HISTORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows[-MAX_DROPS:]), encoding='utf-8')
    temporary.replace(path)


def record_claim(user_id, campaign_id, drop_id, game, name, *, recovered=False, benefits=None):
    identity = f'{user_id}:{campaign_id}:{drop_id}'
    rows = _rows()
    existing = next((row for row in rows if row.get('id') == identity), None)
    if existing:
        if benefits and existing.get('benefits') != benefits:
            existing['benefits'] = benefits
            _write(rows)
        _clear_pending(identity)
        return False
    rows.append(dict(id=identity, user_id=str(user_id), campaign_id=campaign_id, drop_id=drop_id,
                     game=game, drop=name, claim=name, confirmed=True, recovered=recovered, benefits=benefits or [],
                     timestamp=datetime.now(timezone.utc).isoformat()))
    _write(rows)
    stats = load_json(paths.STATS_PATH, {})
    if not isinstance(stats, dict):
        stats = {}
    stats['claims'] = int(stats.get('claims') or 0) + 1
    atomic_write_json(paths.STATS_PATH, stats)
    _clear_pending(identity)
    return True


def enrich_claim(user_id, campaign_id, drop_id, benefits):
    """Refresh artwork only for a known claim; never count old inventory again."""
    if not benefits:
        return
    identity = f'{user_id}:{campaign_id}:{drop_id}'
    rows = _rows()
    existing = next((row for row in rows if row.get('id') == identity), None)
    if existing and existing.get('benefits') != benefits:
        existing['benefits'] = benefits
        _write(rows)


def _clear_pending(identity):
    path = paths.DATA_DIR / 'pending-claims.json'
    items = load_json(path, [])
    atomic_write_json(path, [item for item in items if item != identity] if isinstance(items, list) else [])


def read_claims(user_id):
    rows = _rows()
    return [row for row in reversed(rows) if not row.get('user_id') or row['user_id'] == str(user_id)]
