"""Per-account observed point gains, without treating an existing balance as earnings."""
from datetime import datetime, timezone
from pathlib import Path
from nyxor.storage import load_json, atomic_write_json


class ChannelHistory:
    def __init__(self, path: Path):
        self.path = path
        self.rows = load_json(path, {})
        if not isinstance(self.rows, dict):
            self.rows = {}
        self.active = ""
        self.balance = None

    def begin(self, channel, baseline=None):
        login = str(channel.get("login") or "").casefold()
        if not login:
            return
        now = datetime.now(timezone.utc).isoformat()
        if login != self.active:
            self.active, self.balance = login, baseline
            row = self.rows.setdefault(login, dict(login=login, earned=0, visits=0, first_seen=now))
            row["visits"] += 1
        row = self.rows[login]
        row.update(display_name=channel.get("display_name") or login, game=channel.get("game") or "", last_seen=now)
        atomic_write_json(self.path, self.rows)

    def observe(self, login, balance):
        if login.casefold() != self.active or not self.active:
            return
        balance = max(0, int(balance))
        row = self.rows[self.active]
        if self.balance is not None:
            row["earned"] += max(0, balance - self.balance)
        self.balance = balance
        row["balance"] = balance
        atomic_write_json(self.path, self.rows)

    def end(self):
        self.active, self.balance = "", None


def history_path(user_id):
    from nyxor.paths import DATA_DIR
    if not str(user_id).isdigit():
        raise ValueError("Invalid account ID")
    return DATA_DIR / f"channel-history-{user_id}.json"


def read_history(user_id):
    rows = load_json(history_path(user_id), {})
    return sorted((item for item in rows.values() if isinstance(item, dict)),
                  key=lambda item: item.get("last_seen", ""), reverse=True)
