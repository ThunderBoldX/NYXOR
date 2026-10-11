"""Track only Twitch-confirmed minutes; transport success is not watch credit."""
from __future__ import annotations

import time

from constants import GQL_QUERIES
from nyxor_campaigns import gql_request


async def current_session(session, headers, channel_id):
    result = await gql_request(session, GQL_QUERIES['CurrentDrop'].with_variables({'channelID':str(channel_id)}), headers)
    user = (result.get('data') or {}).get('currentUser') or {}
    current = user.get('dropCurrentSession')
    if current is None:
        return None
    if not isinstance(current, dict):
        raise ValueError('Invalid current Drop session')
    if str((current.get('channel') or {}).get('id') or '') != str(channel_id):
        return None
    minutes = current.get('currentMinutesWatched')
    if type(minutes) is not int or minutes < 0 or not isinstance(current.get('dropID'), str):
        raise ValueError('Invalid current Drop minutes')
    return current


def apply_current_session(state, channel, current):
    """Apply an exact matching Drop only; do not estimate other campaign progress."""
    if not state or not current:
        return
    from nyxor.drop_selection import channel_drops
    for drop in channel_drops(state, channel):
        if drop['drop_id'] == current['dropID']:
            drop['current'] = min(drop['required'], max(drop['current'], current['currentMinutesWatched']))


class ProgressWatch:
    def __init__(self, stall_after=180.0):
        self.stall_after = stall_after
        self.identity = None
        self.minutes = {}
        self.changed_at = 0.0
        self.last_recovery = 0.0

    def reset(self):
        self.identity = None
        self.minutes = {}

    def observe(self, channel, drops, *, now=None, fresh=True):
        now = time.monotonic() if now is None else now
        minutes = {drop['drop_id']:drop['current'] for drop in drops}
        identity = (str(channel.get('channel_id')), str(channel.get('stream_id')), tuple(sorted(minutes)))
        if not fresh or not minutes:
            return dict(status='unknown', recover=False, stalled_seconds=0)
        if identity != self.identity:
            self.identity, self.minutes = identity, minutes
            self.changed_at, self.last_recovery = now, now
            return dict(status='waiting', recover=False, stalled_seconds=0)
        if any(value > self.minutes.get(key, value) for key, value in minutes.items()):
            self.changed_at = now
            self.minutes = minutes
            return dict(status='progressing', recover=False, stalled_seconds=0)
        elapsed = max(0, now - self.changed_at)
        stalled = elapsed >= self.stall_after
        recover = stalled and now - self.last_recovery >= self.stall_after
        if recover:
            self.last_recovery = now
        return dict(status='stalled' if stalled else 'waiting', recover=recover, stalled_seconds=int(elapsed))
