<div align="center">

**🇺🇦 Українська** | [🇬🇧 English](README_EN.md)

# ⚡ NYXOR

### **Nyxor — grinds while you sleep.**

Термінальна автоматизація **Twitch Drops** і **Channel Points**  
для Android через **Termux**.

[![Version](https://img.shields.io/badge/version-1.0.0-7C3AED?style=for-the-badge)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/Android-Termux-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://termux.dev/)
[![Languages](https://img.shields.io/badge/UA-English-2563EB?style=for-the-badge)](#-мови)
[![License](https://img.shields.io/badge/License-MIT-8B5CF6?style=for-the-badge)](LICENSE)

</div>

---

## 🌙 Що вміє NYXOR

NYXOR запускає один легкий Twitch HLS-плеєр і автоматично обирає, що фармити:

1. **Drops завжди мають найвищий пріоритет.**
2. Якщо активних Drops немає — програма переходить до першого онлайн-каналу зі вкладки **«Стримери»** і фармить Channel Points.
3. Коли Drops знову з’являються — NYXOR автоматично повертається до них.

Програма не запускає два паралельні стріми та не потребує відкритого браузера після авторизації.

## ✨ Можливості

| Функція | Стан |
|---|---|
| 🎁 Пошук, прогрес і автоматичний claim Twitch Drops | ✅ |
| 🎮 Пріоритетний список ігор | ✅ |
| 🔎 Пошук точних Twitch-категорій під час введення | ✅ |
| 📺 Пріоритетний список стримерів для Channel Points | ✅ |
| 🔁 Автоматичний перехід Drops ↔ Channel Points | ✅ |
| 🎬 Один низькоякісний HLS-плеєр | ✅ |
| 💰 Нарахування Channel Points | ✅ |
| 🎁 Автоматичний claim бонусних коробочок | ✅ |
| 🔥 Відстеження Watch Streak | ✅ |
| 🎭 Перехід за рейдами без переривання Drops | ✅ |
| 🎬 Автоматичний claim Moments | ✅ |
| 🔮 Predictions з обмеженням ставки | ✅ |
| 🌍 Українська й англійська мови | ✅ |
| 📊 Дашборд, журнал, історія та локальна статистика | ✅ |
| 🔋 Wake lock і необов’язкова телеметрія Termux:API | ✅ |

## 📦 Встановлення

> Рекомендовано використовувати актуальний Termux із F-Droid або GitHub, а не застарілу версію з Google Play.

```bash
pkg update -y && pkg upgrade -y
pkg install git -y
git clone https://github.com/ThunderBoldX/NYXOR.git
cd NYXOR
chmod +x install.sh
./install.sh
```

## 🔐 Перша авторизація

```bash
cd ~/NYXOR
python nyxor_auth.py
```

NYXOR покаже Twitch-код і відкриє сторінку авторизації. Після підтвердження сесія буде локально збережена у `cookies.jar`.

## 🚀 Запуск

```bash
nyxor
```

У програмі:

- у вкладці **«Ігри»** додайте потрібні Twitch-категорії;
- у вкладці **«Стримери»** додайте канали для резервного фарму Channel Points;
- на головній вкладці натисніть **«Запустити»**.

## ⚙️ Логіка роботи

```text
Активні Drops?
├─ Так  → вибрати гру за пріоритетом → знайти канал → фармити Drops + Points
└─ Ні   → знайти першого онлайн-стримера → фармити Channel Points

Під час роботи:
HLS → minute-watched → баланс → claim коробочки → PubSub-події
```

## 🔮 Predictions

Автоматичні Predictions **вимкнені за замовчуванням**, оскільки вони витрачають Channel Points.

Стандартний безпечний профіль:

```json
{
  "enabled": false,
  "strategy": "most_voted",
  "percentage": 2,
  "max_points": 1000,
  "minimum_balance": 5000,
  "reserve_points": 3000,
  "seconds_before_close": 20
}
```

Параметри можна змінити у `nyxor_settings.json`. Перед увімкненням Predictions перевірте значення `max_points` і `reserve_points`.

## 🧪 Діагностика

Перевірка HLS на онлайн-каналі:

```bash
cd ~/NYXOR
python nyxor_hls_test.py LOGIN
```

Семихвилинна перевірка Channel Points:

```bash
python nyxor_points_probe.py LOGIN
```

Розширений тест:

```bash
python nyxor_points_probe.py LOGIN --minutes 20
```

Логи й стан:

```bash
tail -n 150 ~/NYXOR/logs/nyxor.log
cat ~/NYXOR/runtime/state.json
```

## 🔄 Оновлення

```bash
cd ~/NYXOR
git pull
./install.sh
```

`cookies.jar`, `nyxor_settings.json`, історія та локальні журнали не відстежуються Git і не повинні перезаписуватися під час звичайного оновлення.

## 🗑️ Видалення команди

```bash
cd ~/NYXOR
./uninstall.sh
```

Це видаляє команду `nyxor`, але залишає папку проєкту та приватні дані. Повне видалення:

```bash
rm -rf ~/NYXOR
```

## 🔐 Приватність

Не публікуйте й не надсилайте іншим людям:

```text
cookies.jar
nyxor_settings.json
logs/
runtime/
data/
backups/
```

`cookies.jar` містить активну Twitch-сесію. Ці файли виключені через `.gitignore`.

## 📁 Основна структура

```text
NYXOR/
├── nyxor_app.py                 # термінальний інтерфейс
├── nyxor_core.py                # головний цикл Drops + Points
├── nyxor_player.py              # Twitch HLS
├── nyxor_points.py              # баланс і коробочки
├── nyxor_rewards.py             # PubSub, streak, raids, Moments, Predictions
├── nyxor_auth.py                # авторизація Twitch
├── nyxor_hls_test.py            # HLS-діагностика
├── nyxor_points_probe.py        # тест Channel Points
├── nyxor/                       # UI, локалізація, storage, runtime
├── locales/                     # українська й англійська локалізації
├── install.sh
└── nyxor_settings.example.json
```

## 🌍 Мови

- 🇺🇦 Українська
- 🇬🇧 English

Мова перемикається у вкладці **«Налаштування»**. Після зміни перезапустіть інтерфейс.

## ⚠️ Важливо

NYXOR — незалежний неофіційний проєкт, не пов’язаний із Twitch Interactive, Inc. Twitch може змінити API, persisted queries, HLS або механізми винагород, через що окремі функції можуть тимчасово перестати працювати.

Автоматизація може суперечити правилам платформи. Користувач самостійно відповідає за використання програми та ризики для облікового запису.

## ⚖️ Ліцензія


<div align="center">

**Built for Termux. Powered by the night.**

`NYXOR · grinds while you sleep`

</div>
