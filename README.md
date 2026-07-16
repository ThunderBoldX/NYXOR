<div align="center">

**🇺🇦 Українська** | [🇬🇧 English](README_EN.md)


# ⚡ NYXOR

### **Nyxor — grinds while you sleep.**

Термінальний помічник для автоматизованого отримання **Twitch Drops**  
на Android через **Termux**.

<br>

[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Termux-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://termux.dev/)
[![Languages](https://img.shields.io/badge/Language-UA%20%7C%20EN-2563EB?style=for-the-badge)](#languages)
[![License](https://img.shields.io/badge/License-Custom-8B5CF6?style=for-the-badge)](LICENSE)

[![Last commit](https://img.shields.io/github/last-commit/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/commits/main)
[![Repo size](https://img.shields.io/github/repo-size/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR)
[![Issues](https://img.shields.io/github/issues/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/issues)
[![Stars](https://img.shields.io/github/stars/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/stargazers)

<br>

[Про NYXOR](#about) •
[Можливості](#features) •
[Встановлення](#installation) •
[Запуск](#launch) •
[Оновлення](#update) •
[Безпека](#privacy) •
[Ліцензія](#license)

</div>

---

<a id="about"></a>


## 🌙 Що таке NYXOR?

**NYXOR** — це програма для автоматичного отримання **Twitch Drops** на Android через **Termux**.

Вона підійде тим, хто хоче отримувати нагороди з трансляцій, але не хоче постійно тримати Twitch відкритим і вручну перевіряти прогрес.

Ви запускаєте NYXOR, обираєте потрібну кампанію та можете займатися своїми справами. Програма працює у фоні термінала і показує, що відбувається з отриманням нагород.

NYXOR створений спеціально для телефону: без важкого інтерфейсу, зайвих вікон і складного налаштування.

> **Запустив, обрав гру і фармиш Drops.**

---

<a id="features"></a>

## ✨ Можливості

| Можливість | Опис |
|---|---|
| 🎁 **Twitch Drops** | Робота з доступними кампаніями та нагородами Twitch Drops |
| 📺 **Автоматизація** | Менше ручних дій під час пошуку та перегляду відповідних трансляцій |
| 📊 **Прогрес у терміналі** | Зрозумілий статус роботи без браузерного чи графічного інтерфейсу |
| 📱 **Termux-first** | Інтерфейс і запуск оптимізовані саме для Android через Termux |
| 🌐 **Українська та English** | Перемикання мови без окремої версії програми |
| 💾 **Локальні налаштування** | Параметри та дані сесії зберігаються тільки на пристрої |
| 🧾 **Журнал роботи** | Логи допомагають перевірити стан програми та знайти причину помилки |
| ⚙️ **Просте встановлення** | Основне налаштування виконує `install.sh` |
| 🧩 **Власний бренд і структура** | Код, назви файлів та інтерфейс оформлені як самостійний проєкт NYXOR |



<a id="installation"></a>

## 📦 Встановлення

### 1. Оновіть пакети Termux

```bash
pkg update -y && pkg upgrade -y
```

### 2. Встановіть Git

```bash
pkg install git -y
```

### 3. Склонуйте NYXOR

```bash
git clone https://github.com/ThunderBoldX/NYXOR.git
```

### 4. Перейдіть до папки проєкту

```bash
cd NYXOR
```

### 5. Дозвольте запуск інсталятора

```bash
chmod +x install.sh
```

### 6. Запустіть встановлення

```bash
./install.sh
```

Інсталятор підготує необхідні компоненти та перевірить середовище Termux.

---

<a id="launch"></a>

## 🚀 Запуск

```bash
cd ~/NYXOR
./NYXOR
```

Коли програма відкриється вперше, виконайте початкове налаштування
та оберіть потрібну мову інтерфейсу.

---

<a id="update"></a>

## 🔄 Оновлення

Щоб завантажити останні зміни з GitHub:

```bash
cd ~/NYXOR
git pull
./install.sh
```

Після цього запустіть NYXOR звичайною командою:

```bash
./NYXOR
```

---

## 🗑️ Видалення

Щоб повністю видалити програму разом із локальними даними:

```bash
rm -rf ~/NYXOR
```

> ⚠️ Команда безповоротно видалить папку NYXOR, налаштування, сесію,
> історію та локальні журнали роботи.

---

<a id="languages"></a>

## 🌍 Мови

NYXOR підтримує:

- 🇺🇦 **Українську**
- UK **English**

Мову можна змінити в налаштуваннях програми.

---

<a id="privacy"></a>

## 🔐 Приватність і локальні дані

NYXOR створює службові файли безпосередньо на вашому пристрої.
Вони не повинні потрапляти до GitHub або передаватися іншим людям.

До приватних чи тимчасових файлів можуть належати:

```text
cookies.jar
nyxor_settings.json
logs/
history/
*.log
*.pid
__pycache__/
backup/
```

Ці дані виключені з репозиторію через `.gitignore`.

> **Ніколи не публікуйте `cookies.jar` або інші файли сесії.**
> Людина, яка отримає їх, потенційно може використати вашу активну сесію.

NYXOR не потребує публікації пароля Twitch у репозиторії.
Усі персональні дані користувача повинні залишатися лише на його пристрої.

---

## 📁 Структура репозиторію

```text
NYXOR/
├── NYXOR                    # файл запуску програми
├── install.sh               # встановлення та підготовка середовища
├── README.md                # документація проєкту
├── CHANGELOG.md             # історія змін
├── LICENSE                  # умови використання
├── THIRD_PARTY_NOTICES.md   # інформація про сторонні компоненти
└── .gitignore               # виключення приватних і тимчасових файлів
```

Внутрішня структура може розширюватися разом із розвитком проєкту.

---

## 🛠️ Вирішення проблем

<details>
<summary><strong>Permission denied під час запуску</strong></summary>

Надайте файлам право на виконання:

```bash
cd ~/NYXOR
chmod +x NYXOR install.sh
./NYXOR
```

</details>

<details>
<summary><strong>Команда git не знайдена</strong></summary>

Встановіть Git:

```bash
pkg update -y
pkg install git -y
```

</details>

<details>
<summary><strong>Після оновлення програма не запускається</strong></summary>

Повторно запустіть інсталятор:

```bash
cd ~/NYXOR
git pull
chmod +x install.sh NYXOR
./install.sh
```

</details>

<details>
<summary><strong>Сесія Twitch перестала працювати</strong></summary>

Сесії можуть завершуватися або ставати недійсними.
Відкрийте NYXOR та виконайте повторну авторизацію через передбачений
у програмі спосіб. Не надсилайте файл сесії стороннім людям.

</details>

<details>
<summary><strong>Де подивитися причину помилки</strong></summary>

Перевірте повідомлення в терміналі та локальні журнали роботи.
Перед публікацією звіту видаліть із нього токени, cookies,
ідентифікатори сесії та інші приватні дані.

</details>

---

## 🗺️ Напрям розвитку

- [x] Термінальний інтерфейс для Termux
- [x] Українська та англійська локалізація
- [x] Локальне збереження налаштувань
- [x] Окремий інсталятор
- [ ] Подальше покращення стабільності
- [ ] Зручніші повідомлення про помилки
- [ ] Розширена статистика кампаній
- [ ] Сповіщення про завершення або зміну статусу
- [ ] Оформлені GitHub Releases

---

## 🤝 Зворотний зв’язок

Знайшли помилку або маєте ідею?

1. Перевірте, чи немає вже схожого запиту в
   [Issues](https://github.com/ThunderBoldX/NYXOR/issues).
2. Створіть новий Issue.
3. Додайте версію Android, Termux і кроки для повторення проблеми.
4. Не прикріплюйте cookies, токени, паролі або приватні журнали.

Pull Request також підійде, якщо зміни не порушують ліцензію проєкту
та правила використання сторонніх компонентів.

---

<a id="license"></a>

## ⚖️ Ліцензія та сторонні компоненти

NYXOR поширюється на умовах, указаних у файлі [`LICENSE`](LICENSE).

Інформація про використані сторонні компоненти, їхніх авторів
та відповідні ліцензії розміщена у
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

**Copyright © 2026 ThunderBoldX**

---

## ⚠️ Відмова від відповідальності

NYXOR є незалежним неофіційним проєктом і не пов’язаний,
не схвалений та не підтримується Twitch Interactive, Inc.

Назви Twitch, Twitch Drops, логотипи та пов’язані торговельні марки
належать їхнім відповідним власникам.

Функціональність програми може змінюватися або тимчасово переставати
працювати через оновлення Twitch, API, правил платформи чи механізмів
авторизації. Користувач самостійно відповідає за використання програми
та дотримання правил відповідних сервісів.

---

<div align="center">

### ⭐ Подобається NYXOR?

Поставте зірку репозиторію — це допомагає розвитку проєкту.

<br>

**Built for Termux. Powered by the night.**

`NYXOR · grinds while you sleep`

</div>
