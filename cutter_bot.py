import os
import asyncio
import shutil
import time
import subprocess
import math
from uuid import uuid4

from dotenv import load_dotenv
from telegram import Update, InputSticker
from telegram.constants import ParseMode, StickerFormat
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)
from telegram.error import BadRequest, RetryAfter

load_dotenv()

TOKEN    = os.getenv("CUTTER_TOKEN")
TEMP_DIR = "temp_video_tiles"

if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)

WAITING_VIDEO, WAITING_START_PART = range(2)
user_packs: dict[int, list[str]] = {}

# === ПРОГРЕСС-БАР (кастомные эмодзи) ===
E_START  = "<tg-emoji emoji-id='5235855288929652315'>▫️</tg-emoji>"
E_FILLED = "<tg-emoji emoji-id='5235563957002996119'>▪️</tg-emoji>"
E_EMPTY  = "<tg-emoji emoji-id='5233555531511140489'>▫️</tg-emoji>"
E_END    = "<tg-emoji emoji-id='5235566366479650368'>▫️</tg-emoji>"
TOTAL_CELLS = 10


def get_progress_bar_html(percent: float) -> str:
    """Возвращает HTML-строку прогресс-бара из кастомных эмодзи."""
    percent      = max(0.0, min(100.0, percent))
    filled_count = round(TOTAL_CELLS * percent / 100)
    result = ""
    for i in range(TOTAL_CELLS):
        if i < filled_count:
            result += E_FILLED
        elif i == 0:
            result += E_START
        elif i == TOTAL_CELLS - 1:
            result += E_END
        else:
            result += E_EMPTY
    return result


async def safe_update_status(bot, chat_id, message_id, text):
    """Редактирует статусное сообщение; при ошибке шлёт новое."""
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, parse_mode=ParseMode.HTML
        )
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            try:
                msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                return msg.message_id
            except Exception:
                pass
    except Exception:
        pass
    return message_id


# === РАБОТА С ВИДЕО (синхронные функции для run_in_executor) ===

def ffprobe_info(video_path):
    """Возвращает (duration, width, height) видео через ffprobe."""
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
        capture_output=True, text=True
    )
    lines = probe.stdout.strip().split('\n')
    try:
        return float(lines[2]), int(lines[0]), int(lines[1])
    except Exception:
        probe2 = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True
        )
        try:
            return float(probe2.stdout.strip()), 0, 0
        except Exception:
            return 0.0, 0, 0


def scale_video_sync(video_path, scaled_path, target_w, target_h, start_sec, duration):
    """Масштабирует фрагмент видео до target_w×target_h в 60 FPS."""
    ret = subprocess.run(
        ['ffmpeg', '-y', '-ss', str(start_sec), '-i', video_path,
         '-t', str(duration),
         '-vf', f'scale={target_w}:{target_h}:flags=lanczos,fps=60',
         '-c:v', 'libx264', '-preset', 'ultrafast', '-an', scaled_path],
        capture_output=True
    )
    return ret.returncode == 0 and os.path.exists(scaled_path)


def make_tile_webm(scaled_path, tile_path, x, y):
    """Вырезает тайл 100×100 из масштабированного видео и сохраняет как WebM."""
    subprocess.run(
        ['ffmpeg', '-y', '-i', scaled_path,
         '-vf', f'crop=100:100:{x}:{y}',
         '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '40',
         '-auto-alt-ref', '0', '-deadline', 'realtime', '-cpu-used', '8', '-an',
         tile_path],
        capture_output=True
    )
    return os.path.exists(tile_path) and os.path.getsize(tile_path) > 0


def prepare_tiles_sync(scaled_path, tiles_dir, rows, cols, progress_queue):
    """Нарезает масштабированное видео на сетку тайлов rows×cols."""
    os.makedirs(tiles_dir, exist_ok=True)
    total      = rows * cols
    tile_files = []
    for r in range(rows):
        for c in range(cols):
            tile_path = os.path.join(tiles_dir, f"tile_{r:02d}_{c:02d}.webm")
            while not make_tile_webm(scaled_path, tile_path, c * 100, r * 100):
                print(f"[tiles] Не удалось r={r} c={c}, повтор...")
                time.sleep(2)
            tile_files.append((tile_path, "🟦", r, c))
            if progress_queue is not None:
                progress_queue.put_nowait((r * cols + c + 1) / total * 100)
    return tile_files


# === RETRY-ОБЁРТКИ ДЛЯ TELEGRAM API ===

async def create_pack_forever(bot, user_id, pack_name, pack_title, first_path, first_emo):
    """Создаёт стикерпак. Повторяет бесконечно до успеха."""
    attempt = 0
    while True:
        attempt += 1
        try:
            await bot.create_new_sticker_set(
                user_id=user_id,
                name=pack_name,
                title=pack_title,
                stickers=[InputSticker(open(first_path, 'rb'), [first_emo], format=StickerFormat.VIDEO)],
                sticker_type="custom_emoji"
            )
            print(f"[create] OK: {pack_name}")
            return
        except RetryAfter as e:
            print(f"[create] RetryAfter {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 2)
        except BadRequest as e:
            if "already exists" in str(e).lower():
                print(f"[create] Уже существует: {pack_name}")
                return
            wait = min(10 * attempt, 120)
            print(f"[create] BadRequest попытка {attempt}: {e} | жду {wait}s")
            await asyncio.sleep(wait)
        except Exception as e:
            wait = min(10 * attempt, 120)
            print(f"[create] Exception попытка {attempt}: {e} | жду {wait}s")
            await asyncio.sleep(wait)


async def add_sticker_forever(bot, user_id, pack_name, path, emo, scaled_path, x, y, label=""):
    """
    Добавляет стикер в пак. Повторяет бесконечно до успеха.
    При битом файле (INVALID_STICKER и т.п.) — пересоздаёт WebM и пробует снова.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            with open(path, 'rb') as f:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=pack_name,
                    sticker=InputSticker(f, [emo], format=StickerFormat.VIDEO)
                )
            print(f"[add] OK {label} (попытка {attempt})")
            return

        except RetryAfter as e:
            print(f"[add] {label} RetryAfter {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 2)

        except BadRequest as e:
            err = str(e)
            print(f"[add] {label} BadRequest попытка {attempt}: {err}")
            if any(k in err.upper() for k in (
                "INVALID_STICKER", "STICKER_INVALID",
                "WRONG_FILE_TYPE", "BAD_STICKER", "STICKER_FILE_INVALID"
            )):
                print(f"[add] {label} Пересоздаём webm...")
                loop = asyncio.get_event_loop()
                ok = await loop.run_in_executor(None, make_tile_webm, scaled_path, path, x, y)
                if not ok:
                    print(f"[add] {label} Не удалось пересоздать, жду 5s")
                    await asyncio.sleep(5)
                continue
            await asyncio.sleep(min(5 * attempt, 60))

        except Exception as e:
            print(f"[add] {label} Exception попытка {attempt}: {e} | жду {min(5 * attempt, 60)}s")
            await asyncio.sleep(min(5 * attempt, 60))


# === ХЕНДЛЕРЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 <b>Видео → Эмодзи Конвертер</b>\n\n"
        "Превращаю видео в сетку из <b>анимированных кастомных эмодзи</b>!\n\n"
        "📐 Ширина 800px — 8 эмодзи в ряд\n"
        "🎬 60 FPS · каждые 3 секунды = отдельный пак\n\n"
        "🗑 /delete_packs — удалить все созданные паки\n\n"
        "👇 <b>Отправь видео!</b>",
        parse_mode=ParseMode.HTML,
    )
    return WAITING_VIDEO


async def delete_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot     = context.bot
    packs   = list(user_packs.get(user_id, []))

    if not packs:
        await update.message.reply_text("У тебя нет паков для удаления.")
        return

    msg = await update.message.reply_text(
        f"🗑 Удаляю <b>{len(packs)}</b> паков...", parse_mode=ParseMode.HTML
    )
    deleted = 0
    for pack_name in packs:
        for _ in range(10):
            try:
                await bot.delete_sticker_set(pack_name)
                deleted += 1
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                if "not found" in str(e).lower() or "invalid" in str(e).lower():
                    deleted += 1
                    break
                await asyncio.sleep(2)
        await asyncio.sleep(0.3)

    user_packs[user_id] = []
    await safe_update_status(
        bot, update.effective_chat.id, msg.message_id,
        f"✅ Удалено паков: <b>{deleted}</b>"
    )


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.animation or update.message.document
    if not video:
        await update.message.reply_text("❌ Пришли видео-файл.")
        return WAITING_VIDEO

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    bot     = context.bot

    unique_id  = uuid4().hex[:8]
    user_dir   = os.path.join(TEMP_DIR, f"{user_id}_{unique_id}")
    os.makedirs(user_dir, exist_ok=True)
    video_path = os.path.join(user_dir, "input.mp4")

    msg    = await update.message.reply_text("📥 <b>Скачиваю видео...</b>", parse_mode=ParseMode.HTML)
    msg_id = msg.message_id

    file = await video.get_file()
    await file.download_to_drive(video_path)

    await safe_update_status(bot, chat_id, msg_id, "🔍 <b>Анализирую видео...</b>")
    loop = asyncio.get_running_loop()
    dur, orig_w, orig_h = await loop.run_in_executor(None, ffprobe_info, video_path)

    if dur <= 0 or orig_w <= 0:
        await safe_update_status(bot, chat_id, msg_id, "❌ Не удалось прочитать видео.")
        shutil.rmtree(user_dir, ignore_errors=True)
        return ConversationHandler.END

    PART_DURATION = 3.0
    num_parts = max(1, math.ceil(dur / PART_DURATION))

    context.user_data.update({
        'video_path': video_path,
        'user_dir':   user_dir,
        'unique_id':  unique_id,
        'dur':        dur,
        'orig_w':     orig_w,
        'orig_h':     orig_h,
        'num_parts':  num_parts,
        'msg_id':     msg_id,
        'chat_id':    chat_id,
    })

    await safe_update_status(
        bot, chat_id, msg_id,
        f"🎬 <b>Видео проанализировано!</b>\n\n"
        f"⏱ Длительность: <b>{dur:.1f} сек</b>\n"
        f"📦 Всего фрагментов (по 3 сек): <b>{num_parts}</b>\n\n"
        f"С какого фрагмента начать? Введи номер от <b>1</b> до <b>{num_parts}</b>:"
    )
    return WAITING_START_PART


async def receive_start_part(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot     = context.bot
    chat_id = context.user_data.get('chat_id') or update.effective_chat.id
    msg_id  = context.user_data.get('msg_id')
    user_id = update.effective_user.id

    num_parts = context.user_data.get('num_parts', 1)
    text      = update.message.text.strip()

    if not text.isdigit() or not (1 <= int(text) <= num_parts):
        await update.message.reply_text(
            f"❌ Введи целое число от <b>1</b> до <b>{num_parts}</b>.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_START_PART

    start_part_idx = int(text) - 1

    video_path = context.user_data['video_path']
    user_dir   = context.user_data['user_dir']
    unique_id  = context.user_data['unique_id']
    dur        = context.user_data['dur']
    orig_w     = context.user_data['orig_w']
    orig_h     = context.user_data['orig_h']

    loop = asyncio.get_running_loop()

    msg_id = await safe_update_status(
        bot, chat_id, msg_id,
        f"🚀 <b>Начинаю обработку с фрагмента {start_part_idx + 1}/{num_parts}...</b>"
    )

    target_w = 800
    target_h = int(math.ceil((orig_h / orig_w * target_w) / 100.0)) * 100
    cols     = target_w // 100
    rows     = target_h // 100

    PART_DURATION = 3.0
    num_parts     = max(1, math.ceil(dur / PART_DURATION))

    bot_me           = await bot.get_me()
    pack_links       = []
    preview_stickers = None

    if user_id not in user_packs:
        user_packs[user_id] = []

    for part_idx in range(start_part_idx, num_parts):
        start_sec = part_idx * PART_DURATION
        part_dur  = min(PART_DURATION, dur - start_sec)
        if part_dur <= 0.1:
            break

        part_num   = part_idx + 1
        part_label = f"часть {part_num}/{num_parts}"

        # Масштабируем — вечный retry
        scaled_path = os.path.join(user_dir, f"scaled_{part_idx}.mp4")
        tiles_dir   = os.path.join(user_dir, f"tiles_{part_idx}")

        msg_id = await safe_update_status(
            bot, chat_id, msg_id,
            f"🎞 <b>Масштабирую {part_label}...</b>\n\n{get_progress_bar_html(0)} 0%"
        )

        while True:
            ok = await loop.run_in_executor(
                None, scale_video_sync,
                video_path, scaled_path, target_w, target_h, start_sec, part_dur
            )
            if ok:
                break
            print(f"[scale] {part_label} не удалось, повтор через 5s")
            await asyncio.sleep(5)

        # Нарезаем тайлы
        progress_queue = asyncio.Queue()
        future = loop.run_in_executor(
            None, prepare_tiles_sync,
            scaled_path, tiles_dir, rows, cols, progress_queue
        )

        last_update = 0
        while not future.done():
            try:
                pct = progress_queue.get_nowait()
                if time.time() - last_update > 2.0:
                    bar    = get_progress_bar_html(pct)
                    msg_id = await safe_update_status(
                        bot, chat_id, msg_id,
                        f"✂️ <b>Создаю эмодзи — {part_label}</b>\n\n{bar} {int(pct)}%"
                    )
                    last_update = time.time()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.2)

        tile_files = await future

        # Создаём пак
        pack_name  = f"vt{part_num}_{user_id}_{unique_id}_by_{bot_me.username}"[:64].rstrip('_')
        pack_title = f"🎬 Video Tiles {unique_id[:5]} ({part_num}/{num_parts})"

        msg_id = await safe_update_status(
            bot, chat_id, msg_id,
            f"🚀 <b>Создаю пак — {part_label}...</b>"
        )

        first_path, first_emo, _, _ = tile_files[0]
        await create_pack_forever(bot, user_id, pack_name, pack_title, first_path, first_emo)
        user_packs[user_id].append(pack_name)

        # Загружаем остальные тайлы
        uploaded    = 1
        total_tiles = len(tile_files)
        last_update = 0

        msg_id = await safe_update_status(
            bot, chat_id, msg_id,
            f"🚀 <b>Загружаю эмодзи — {part_label}...</b>\n\n"
            f"{get_progress_bar_html(0)} 0%\n<i>1/{total_tiles} эмодзи</i>"
        )

        for path, emo, r, c in tile_files[1:]:
            await add_sticker_forever(
                bot, user_id, pack_name, path, emo,
                scaled_path, c * 100, r * 100,
                label=f"{part_label} r{r}c{c}"
            )
            uploaded += 1

            if time.time() - last_update > 3.0 or uploaded == total_tiles:
                pct    = int(uploaded / total_tiles * 100)
                bar    = get_progress_bar_html(pct)
                msg_id = await safe_update_status(
                    bot, chat_id, msg_id,
                    f"🚀 <b>Загружаю эмодзи — {part_label}</b>\n\n"
                    f"{bar} {pct}%\n<i>{uploaded}/{total_tiles} эмодзи</i>"
                )
                last_update = time.time()

        link = f"https://t.me/addemoji/{pack_name}"
        pack_links.append((link, part_num, num_parts))

        if preview_stickers is None:
            try:
                sset = await bot.get_sticker_set(pack_name)
                preview_stickers = (sset.stickers, cols)
            except Exception:
                pass

        shutil.rmtree(tiles_dir, ignore_errors=True)
        try:
            os.remove(scaled_path)
        except Exception:
            pass

    # === ФИНАЛ ===
    if not pack_links:
        await safe_update_status(bot, chat_id, msg_id, "❌ Не удалось создать ни одного пака.")
        shutil.rmtree(user_dir, ignore_errors=True)
        return ConversationHandler.END

    links_html = ""
    for link, pnum, pmax in pack_links:
        links_html += f"📦 <a href='{link}'>Часть {pnum}/{pmax}</a>\n"

    preview_html = ""
    if preview_stickers:
        stickers, pcols = preview_stickers
        line_buf = ""
        shown = 0
        for i, s in enumerate(stickers):
            if shown >= pcols * 2:
                break
            line_buf += f"<tg-emoji emoji-id='{s.custom_emoji_id}'>🟦</tg-emoji>"
            shown += 1
            if (i + 1) % pcols == 0:
                preview_html += line_buf + "\n"
                line_buf = ""
        if line_buf:
            preview_html += line_buf

    finish_text = (
        f"✅ <b>Готово!</b> Паков эмодзи: <b>{len(pack_links)}</b>\n\n"
        f"🔗 <b>Ссылки:</b>\n{links_html}\n"
        f"<b>Превью первой части:</b>\n{preview_html}\n\n"
        f"🗑 /delete_packs — удалить все паки"
    )

    if len(finish_text) <= 4096:
        await safe_update_status(bot, chat_id, msg_id, finish_text)
    else:
        await safe_update_status(
            bot, chat_id, msg_id,
            f"✅ <b>Готово!</b> Паков: <b>{len(pack_links)}</b>\n\n"
            f"🔗 <b>Ссылки:</b>\n{links_html}\n\n"
            f"🗑 /delete_packs"
        )
        if preview_html:
            await bot.send_message(
                chat_id=chat_id,
                text=f"<b>Превью первой части:</b>\n{preview_html}",
                parse_mode=ParseMode.HTML
            )

    shutil.rmtree(user_dir, ignore_errors=True)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⛔️ Отмена.")
    return ConversationHandler.END


def main():
    application = Application.builder().token(TOKEN).concurrent_updates(True).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.VIDEO | filters.Document.VIDEO | filters.ANIMATION, receive_video),
        ],
        states={
            WAITING_VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO | filters.ANIMATION, receive_video)
            ],
            WAITING_START_PART: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_part)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv)
    application.add_handler(CommandHandler("delete_packs", delete_packs))

    print("🚀 Cutter Bot started...")
    application.run_polling()


if __name__ == "__main__":
    main()
