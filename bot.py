import asyncio
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import RetryAfter, BadRequest, TimedOut

load_dotenv()

# === НАСТРОЙКИ ===
MAIN_TOKEN = os.getenv("MAIN_TOKEN")       # Главный бот (Controller)
CHAT_ID    = int(os.getenv("CHAT_ID"))     # ID группы/канала
COLS       = 8                             # Кол-во эмодзи в ряд
BATCH_SIZE = 7                             # Смена бота каждые N кадров

WORKER_TOKENS = [
    MAIN_TOKEN,
    os.getenv("WORKER_TOKEN_1"),
    os.getenv("WORKER_TOKEN_2"),
    os.getenv("WORKER_TOKEN_3"),
    os.getenv("WORKER_TOKEN_4"),
]

# === СПИСОК СТИКЕРПАКОВ (73 кадра) ===
FIXED_PACKS = [
    "vt1_8358905577_bf8e020f_by_BadAppleVideobot",  "vt2_8358905577_bf8e020f_by_BadAppleVideobot",
    "vt3_8358905577_bf8e020f_by_BadAppleVideobot",  "vt4_8358905577_bf8e020f_by_BadAppleVideobot",
    "vt5_8358905577_bf8e020f_by_BadAppleVideobot",  "vt6_8358905577_bf8e020f_by_BadAppleVideobot",
    "vt7_8358905577_bf8e020f_by_BadAppleVideobot",  "vt8_8358905577_bf8e020f_by_BadAppleVideobot",
    "vt9_8358905577_bf8e020f_by_BadAppleVideobot",  "vt10_8358905577_bf8e020f_by_BadAppleVideobot",
    "vt11_8563516348_3ab6845a_by_BadAppleVideobot", "vt12_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt13_8563516348_3ab6845a_by_BadAppleVideobot", "vt14_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt15_8563516348_3ab6845a_by_BadAppleVideobot", "vt16_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt17_8563516348_3ab6845a_by_BadAppleVideobot", "vt18_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt19_8563516348_3ab6845a_by_BadAppleVideobot", "vt20_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt21_8563516348_3ab6845a_by_BadAppleVideobot", "vt22_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt23_8563516348_3ab6845a_by_BadAppleVideobot", "vt24_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt25_8563516348_3ab6845a_by_BadAppleVideobot", "vt26_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt27_8563516348_3ab6845a_by_BadAppleVideobot", "vt28_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt29_8563516348_3ab6845a_by_BadAppleVideobot", "vt30_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt31_8563516348_3ab6845a_by_BadAppleVideobot", "vt32_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt33_8563516348_3ab6845a_by_BadAppleVideobot", "vt34_8563516348_3ab6845a_by_BadAppleVideobot",
    "vt35_8492905491_f9ce34b1_by_BadAppleVideobot", "vt36_8492905491_f9ce34b1_by_BadAppleVideobot",
    "vt37_8492905491_f9ce34b1_by_BadAppleVideobot", "vt38_8492905491_f9ce34b1_by_BadAppleVideobot",
    "vt39_8492905491_f9ce34b1_by_BadAppleVideobot", "vt40_8492905491_f9ce34b1_by_BadAppleVideobot",
    "vt41_8492905491_f9ce34b1_by_BadAppleVideobot", "vt42_8492905491_f9ce34b1_by_BadAppleVideobot",
    "vt43_8492905491_f9ce34b1_by_BadAppleVideobot", "vt44_8492905491_f9ce34b1_by_BadAppleVideobot",
    "vt45_7917311444_8d56ff16_by_BadAppleVideobot", "vt46_7917311444_8d56ff16_by_BadAppleVideobot",
    "vt47_7917311444_8d56ff16_by_BadAppleVideobot", "vt48_7917311444_8d56ff16_by_BadAppleVideobot",
    "vt49_7917311444_8d56ff16_by_BadAppleVideobot", "vt50_7917311444_8d56ff16_by_BadAppleVideobot",
    "vt51_7917311444_8d56ff16_by_BadAppleVideobot", "vt52_7917311444_8d56ff16_by_BadAppleVideobot",
    "vt53_7917311444_8d56ff16_by_BadAppleVideobot", "vt54_7917311444_8d56ff16_by_BadAppleVideobot",
    "vt55_8358905577_e01524ae_by_kolia_robot",      "vt56_8358905577_e01524ae_by_kolia_robot",
    "vt57_8358905577_e01524ae_by_kolia_robot",      "vt58_8358905577_e01524ae_by_kolia_robot",
    "vt59_8358905577_e01524ae_by_kolia_robot",      "vt60_8358905577_e01524ae_by_kolia_robot",
    "vt61_8358905577_e01524ae_by_kolia_robot",      "vt62_8358905577_e01524ae_by_kolia_robot",
    "vt63_8358905577_e01524ae_by_kolia_robot",      "vt64_8358905577_e01524ae_by_kolia_robot",
    "vt65_8563516348_53aead51_by_kolia_robot",      "vt66_8563516348_53aead51_by_kolia_robot",
    "vt67_8563516348_53aead51_by_kolia_robot",      "vt68_8563516348_53aead51_by_kolia_robot",
    "vt69_8563516348_53aead51_by_kolia_robot",      "vt70_8563516348_53aead51_by_kolia_robot",
    "vt71_8563516348_53aead51_by_kolia_robot",      "vt72_8563516348_53aead51_by_kolia_robot",
    "vt73_8563516348_53aead51_by_kolia_robot",
]

# Глобальный контроль сессий
sessions: dict[int, bool] = {}


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def build_emoji_html(bot: Bot, pack_name: str) -> str | None:
    """
    Загружает стикерпак и формирует HTML-строку с кастомными эмодзи
    в виде сетки COLS x N.
    """
    try:
        sset = await bot.get_sticker_set(pack_name)
    except Exception as e:
        print(f"[Error] Pack {pack_name} fetch failed: {e}")
        return None

    if not sset.stickers:
        return None

    html_parts = []
    for i, s in enumerate(sset.stickers):
        html_parts.append(f"<tg-emoji emoji-id='{s.custom_emoji_id}'>🟦</tg-emoji>")
        if (i + 1) % COLS == 0:
            html_parts.append("\n")

    return "".join(html_parts).strip()


def format_text(current_idx: int, total: int, grid: str) -> str:
    """Формирует итоговый текст кадра с заголовком и сеткой."""
    return (
        f"BAD APPLE: RUNNING [{current_idx}/{total}]\n"
        f"----------------------------------------\n"
        f"{grid}\n"
        f"----------------------------------------"
    )


# === ОСНОВНАЯ ЛОГИКА АНИМАЦИИ ===

async def run_animation(controller_bot: Bot, user_id: int, user_chat_id: int):
    """
    Проигрывает анимацию Bad Apple через 5 ботов поочерёдно,
    чтобы не упираться в лимиты Telegram Bot API.
    """
    workers = [Bot(token=t) for t in WORKER_TOKENS]
    total = len(FIXED_PACKS)

    last_msg_id = None
    last_bot = None

    for i, pack_name in enumerate(FIXED_PACKS):
        if not sessions.get(user_id, False):
            break

        worker_idx  = (i // BATCH_SIZE) % len(workers)
        current_bot = workers[worker_idx]

        html_grid = await build_emoji_html(current_bot, pack_name)
        if not html_grid:
            print(f"Skipping frame {i + 1} (no grid)")
            continue

        full_text    = format_text(i + 1, total, html_grid)
        is_new_batch = (i % BATCH_SIZE == 0)

        success     = False
        retry_count = 0

        while not success and retry_count < 3:
            try:
                if is_new_batch:
                    if last_msg_id and last_bot:
                        try:
                            await last_bot.delete_message(chat_id=CHAT_ID, message_id=last_msg_id)
                        except Exception as e:
                            print(f"Delete error: {e}")

                    msg = await current_bot.send_message(
                        chat_id=CHAT_ID,
                        text=full_text,
                        parse_mode=ParseMode.HTML,
                    )
                    last_msg_id = msg.message_id
                    last_bot    = current_bot
                    success     = True

                else:
                    await current_bot.edit_message_text(
                        chat_id=CHAT_ID,
                        message_id=last_msg_id,
                        text=full_text,
                        parse_mode=ParseMode.HTML,
                    )
                    success = True

            except RetryAfter as e:
                print(f"FloodLimit ({e.retry_after}s). Sleeping...")
                await asyncio.sleep(e.retry_after + 1)
                retry_count += 1
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    success = True
                else:
                    print(f"Bad Request: {e}")
                    retry_count += 1
                    await asyncio.sleep(1)
            except TimedOut:
                retry_count += 1
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Critical error on frame {i + 1}: {e}")
                retry_count += 1
                await asyncio.sleep(1)

        await asyncio.sleep(3)

    # Завершение
    if sessions.get(user_id, False):
        if last_bot and last_msg_id:
            try:
                await last_bot.edit_message_text(
                    chat_id=CHAT_ID,
                    message_id=last_msg_id,
                    text="🎬 <b>BAD APPLE: COMPLETED</b>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

        try:
            await controller_bot.send_message(
                chat_id=user_chat_id,
                text="✅ <b>Готово!</b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    sessions[user_id] = False


# === ХЕНДЛЕРЫ КОМАНД ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Multi-Bot Bad Apple Player</b>\n\n"
        "Система использует 5 ботов для обхода лимитов Telegram.\n"
        "Убедитесь, что все 5 ботов — администраторы в канале!\n\n"
        "/launch — Запустить анимацию\n"
        "/stop   — Остановить анимацию",
        parse_mode=ParseMode.HTML,
    )


async def launch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 START BAD APPLE", callback_data=f"run:{user_id}")
    ]])

    await update.message.reply_text(
        f"✅ Готов к запуску.\n"
        f"Кадров: <b>{len(FIXED_PACKS)}</b> | Ботов: <b>{len(WORKER_TOKENS)}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = update.effective_user.id
    owner_id = int(query.data.split(":")[1])

    if not query.data.startswith("run:"):
        return

    if user_id != owner_id:
        await query.answer("❌ Не твой процесс!", show_alert=True)
        return

    if sessions.get(user_id, False):
        await query.answer("▶️ Уже работает!")
        return

    sessions[user_id] = True
    await query.answer("▶️ Погнали!")
    await query.edit_message_text(
        "▶️ <b>Анимация запущена в канале!</b>\nСледите за эфиром.",
        parse_mode=ParseMode.HTML,
    )

    asyncio.create_task(run_animation(context.bot, user_id, query.message.chat_id))


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if sessions.get(user_id, False):
        sessions[user_id] = False
        await update.message.reply_text("🛑 Команда остановки принята. Завершаю...")
    else:
        await update.message.reply_text("💤 Ничего не запущено.")


# === ТОЧКА ВХОДА ===

def main():
    app = Application.builder().token(MAIN_TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("launch", launch))
    app.add_handler(CommandHandler("stop",   stop))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^run:"))

    print("🤖 Controller Bot started. Waiting for commands...")
    app.run_polling()


if __name__ == "__main__":
    main()
