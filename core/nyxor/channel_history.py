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
        self.rows = load_json(self.path, {})
        if not isinstance(self.rows, dict):
            self.rows = {}
        now = datetime.now(timezone.utc).isoformat()
        # A removed active row stays hidden until this viewing session ends.
        if login == self.active and login not in self.rows:
            self.balance = None
            return
        if login != self.active or login not in self.rows:
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
        self.rows = load_json(self.path, {})
        if not isinstance(self.rows, dict) or self.active not in self.rows:
            self.balance = None
            return
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
    if not isinstance(rows, dict):
        return []
    return sorted((item for item in rows.values() if isinstance(item, dict)),
                  key=lambda item: item.get("last_seen", ""), reverse=True)


def delete_history(user_id, logins):
    path = history_path(user_id)
    rows = load_json(path, {})
    if not isinstance(rows, dict):
        rows = {}
    removed = {str(login).casefold() for login in logins}
    atomic_write_json(path, {key: row for key, row in rows.items() if key.casefold() not in removed})
