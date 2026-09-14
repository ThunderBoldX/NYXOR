"""Public farming status for the Android foreground notification."""


def notification_status(snapshot: dict) -> dict:
    en = snapshot.get("settings", {}).get("language") == "en"
    def tr(uk, english):
        return english if en else uk
    def result(title, text, details="", progress=None):
        return dict(title="NYXOR · " + title, text=text, details=details or text, progress=progress)
    if not snapshot.get("running"):
        return result(tr("На паузі", "Paused"), tr("Фарм зупинено", "Farming stopped"))
    if snapshot.get("network") in {"offline", "no_internet", "captive"}:
        return result(tr("Очікуємо інтернет", "Waiting for internet"),
                      tr("Фарм продовжиться після підключення", "Farming will resume when connected"))
    state = snapshot.get("state") or {}
    meta = state.get("_meta") or {}
    if meta.get("error"):
        return result(tr("Відновлюємо з’єднання", "Reconnecting"),
                      tr("Повторна спроба підключення до Twitch", "Retrying connection to Twitch"))
    game = str(state.get("game") or "")
    channel = str(state.get("channel") or "")
    context = " · ".join(value for value in (game, channel) if value and value != "—")
    if not context:
        return result(tr("Шукаємо стрім", "Finding a stream"),
                      tr("Перевіряємо чергу та доступні кампанії", "Checking the queue and available campaigns"))
    lines = [context]
    progress = None
    for drop in (state.get("active_drops") or [])[:3]:
        try:
            required = float(drop.get("required", 0))
            current = max(0, float(drop.get("current", 0)))
            if required <= 0:
                continue
            percent = min(100, max(0, int(current * 100 / required)))
            if progress is None:
                progress = percent
            lines.append(f"{drop.get('drop') or 'Drop'} · {percent}% · {min(current, required):g}/{required:g} " + tr("хв", "min"))
        except (ValueError, TypeError, OverflowError):
            continue
    if state.get("mode") == "points":
        lines.append(tr("Бали каналу: ", "Channel points: ") + str(state.get("points") or "—"))
    summary = context + (f" · {progress}%" if progress is not None else "")
    return result(tr("Фарм працює", "Farming"), summary, "\n".join(lines), progress)
