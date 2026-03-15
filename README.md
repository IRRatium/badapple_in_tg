# 🎬 Bad Apple Telegram Bots

Два бота для воспроизведения анимации через кастомные эмодзи Telegram:

| Файл | Что делает |
|---|---|
| `bot.py` | **Проигрыватель** — воспроизводит готовую анимацию Bad Apple в чате |
| `cutter_bot.py` | **Нарезатель** — превращает любое видео в стикерпаки с анимированными эмодзи |

---

## Как это работает

### Проигрыватель (`bot.py`)

Каждый «кадр» анимации — отдельный стикерпак с кастомными эмодзи, выстроенными в сетку 8×N.  
Пять ботов работают по очереди, чтобы обойти лимиты Telegram Bot API.

```
Пользователь → /launch → Controller Bot
                               ↓
               Worker 1 → Worker 2 → Worker 3 → ... (по кругу, каждые 7 кадров)
                               ↓
                         Telegram-чат
```

### Нарезатель (`cutter_bot.py`)

```
Видео → ffmpeg (масштаб 800px, 60FPS) → сетка тайлов 100×100px → WebM → стикерпаки
```

Каждые 3 секунды видео → один пак. Все тайлы внутри пака — кастомные эмодзи сетки.

---

## Структура репозитория

```
.
├── bot.py            # Проигрыватель Bad Apple (5 ботов)
├── cutter_bot.py     # Нарезатель видео в эмодзи
├── .env.example      # Шаблон переменных окружения
├── .gitignore        # Исключения для git
├── requirements.txt  # Python-зависимости
└── README.md         # Этот файл
```

---

## Установка и запуск

### 1. Установить Python 3.11+

**Windows:** скачай с [python.org](https://python.org), при установке поставь галочку **«Add Python to PATH»**.

**Linux / macOS:**
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install python3 python3-pip python3-venv -y

# macOS (через Homebrew)
brew install python
```

Проверка:
```
python --version        # Windows
python3 --version       # Linux / macOS
```

---

### 2. Установить ffmpeg

Нужен только для `cutter_bot.py`.

**Windows:**
1. Скачай архив с [ffmpeg.org](https://ffmpeg.org/download.html) (сборка от gyan.dev или BtbN)
2. Распакуй, например, в `C:\ffmpeg`
3. Добавь `C:\ffmpeg\bin` в переменную среды `PATH`:  
   Пуск → «Переменные среды» → `Path` → Изменить → Добавить

**Linux:**
```bash
sudo apt install ffmpeg -y        # Ubuntu / Debian
sudo dnf install ffmpeg -y        # Fedora
```

**macOS:**
```bash
brew install ffmpeg
```

Проверка:
```
ffmpeg -version
```

---

### 3. Клонировать репозиторий

```bash
git clone https://github.com/IRRatium/badapple_in_tg.git
cd ВАШ_РЕПО
```

---

### 4. Создать виртуальное окружение

**Windows (cmd / PowerShell):**
```
python -m venv venv
venv\Scripts\activate
```

> Если PowerShell ругается на политику выполнения скриптов:
> ```
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

После активации в начале строки появится `(venv)`.

---

### 5. Установить зависимости

```
pip install -r requirements.txt
```

---

### 6. Настроить `.env`

Скопируй шаблон и заполни своими токенами:

**Windows:**
```
copy .env.example .env
notepad .env
```

**Linux / macOS:**
```bash
cp .env.example .env
nano .env        # или: vim .env / code .env
```

Пример заполненного `.env`:
```
MAIN_TOKEN=1234567890:AABBccDDeeFF...
WORKER_TOKEN_1=9876543210:AAZZyyXXwwVV...
WORKER_TOKEN_2=...
WORKER_TOKEN_3=...
WORKER_TOKEN_4=...
CHAT_ID=-1001234567890

CUTTER_TOKEN=1122334455:AAMMnnOOppQQ...
```

> **Где взять токены** — [@BotFather](https://t.me/BotFather), команда `/newbot`.  
> **Где взять CHAT_ID** — перешли любое сообщение из чата боту [@userinfobot](https://t.me/userinfobot).

---

### 7. Добавить ботов в чат

Для `bot.py` — все 5 ботов должны быть администраторами чата с правами **«Публикация»** и **«Редактирование сообщений»**.

---

### 8. Запустить

**Проигрыватель:**
```
python bot.py          # Windows
python3 bot.py         # Linux / macOS
```

**Нарезатель:**
```
python cutter_bot.py   # Windows
python3 cutter_bot.py  # Linux / macOS
```

Оба бота можно запускать одновременно в разных терминалах.

---

## Команды ботов

### Проигрыватель (`bot.py`)

| Команда | Описание |
|---|---|
| `/start` | Справка |
| `/launch` | Подготовить и запустить анимацию |
| `/stop` | Остановить |

### Нарезатель (`cutter_bot.py`)

| Команда | Описание |
|---|---|
| `/start` | Справка |
| `/delete_packs` | Удалить все созданные паки |
| `/cancel` | Отменить текущую обработку |
| *(отправить видео)* | Начать нарезку |

---

## Конфигурация

В `bot.py`:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `COLS` | `8` | Эмодзи в одной строке |
| `BATCH_SIZE` | `7` | Кадров до смены рабочего бота |

В `cutter_bot.py`:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `PART_DURATION` | `3.0` сек | Длина одного пака |
| `target_w` | `800` px | Ширина кадра (8 эмодзи × 100px) |

---

## Зависимости

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21+
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [ffmpeg](https://ffmpeg.org) (только для `cutter_bot.py`)

---

## Лицензия

Проект распространяется под лицензией **MIT**.

### Что это значит на практике

**Можно:**
- Использовать бесплатно — в личных и коммерческих проектах
- Изменять код под свои нужды
- Распространять оригинал или свои модификации
- Включать в другие проекты, в том числе закрытые

**Нельзя:**
- Удалять упоминание авторства из исходного кода

**Не гарантируется:**
- Работоспособность — код предоставляется «как есть» (as is), без каких-либо гарантий

MIT — самая простая и свободная лицензия. Если ты форкаешь или публично переиспользуешь проект, достаточно оставить строчку с именем автора в коде или README.

---

## Важно

- Файл `.env` **никогда не попадает в git** — прописан в `.gitignore`
- Не передавай токены ботов третьим лицам
- Анимация рассчитана на **73 стикерпака** (~219 секунд при задержке 3с/кадр)
