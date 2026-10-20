import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message
from dotenv import load_dotenv

from bot.keyboard import (
    card_kb,
    finale_kb,
    main_menu_kb,
    map_kb,
    progress_kb,
    quiz_kb,
    yandex_map_kb,
)

from bot.points import (
    ABOUT_TEXT,
    FINAL_SUMMARY,
    MAP_URL,
    POINTS,
    QUIZ,
    ROUTE_INTRO,
    ROUTE_TITLE,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(".env")
TOKEN = os.environ.get("BOT_TOKEN")

PHOTOS_DIR = BASE_DIR /"bot" / "img"
STATE_FILE = BASE_DIR / "state.json"
TOTAL = len(POINTS)

dp = Dispatcher()


# ---------------------------------------------------------------- состояние
# {chat_id: {"current": int, "visited": [int], "quiz_score": int, "quiz_next": int}}
_state: dict[str, dict] = {}


def load_state() -> None:
    if STATE_FILE.exists():
        _state.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))


def save_state() -> None:
    STATE_FILE.write_text(
        json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_user(chat_id: int) -> dict:
    key = str(chat_id)
    if key not in _state:
        _state[key] = {"current": 0, "visited": [], "quiz_score": 0, "quiz_next": 0}
        save_state()
    return _state[key]


async def send_start(bot: Bot, chat_id: int) -> None:
    text = (
        f"{html.bold(html.quote(ROUTE_TITLE))}\n"
        f"{html.quote(ROUTE_INTRO)}\n\n"
        f"{TOTAL} остановок, около 40 минут чтения."
    )
    await bot.send_message(chat_id, text, reply_markup=main_menu_kb())


async def send_card(bot: Bot, chat_id: int, idx: int) -> None:
    """Фото отдельно (подпись к фото ограничена 1024 символами), текст отдельным сообщением."""
    p = POINTS[idx]
    user = get_user(chat_id)
    user["current"] = idx
    save_state()

    photo_path = PHOTOS_DIR / p["photo"] if p.get("photo") else None
    if photo_path and photo_path.exists():
        await bot.send_photo(chat_id, FSInputFile(photo_path))

    text = (
        f"{html.bold(f'Остановка {idx + 1} из {TOTAL}')}\n"
        f"{html.bold(html.quote(p['title']))}\n\n"
        f"{html.bold('Что это')}\n{html.quote(p['what'])}\n\n"
        f"{html.bold('Почему важно')}\n{html.quote(p['why'])}\n\n"
        f"{html.bold('Интересный факт')}\n{html.quote(p['fact'])}\n\n"
        f"{html.italic('Источник: ' + html.quote(p['source']))}"
    )
    await bot.send_message(
        chat_id, text, reply_markup=card_kb(idx, idx in user["visited"])
    )


async def send_map(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "Карта маршрута со всеми точками:",
        reply_markup=map_kb(MAP_URL),
    )


async def send_progress(bot: Bot, chat_id: int) -> None:
    visited = set(get_user(chat_id)["visited"])
    done = len(visited)
    lines = [f"Пройдено {done} из {TOTAL}", "▰" * done + "▱" * (TOTAL - done), ""]
    for i, p in enumerate(POINTS):
        mark = "✅" if i in visited else "⬜️"
        lines.append(f"{mark} {i + 1}. {html.quote(p['title'])}")

    await bot.send_message(chat_id, "\n".join(lines), reply_markup=progress_kb(TOTAL))


async def send_finale(bot: Bot, chat_id: int) -> None:
    done = len(get_user(chat_id)["visited"])
    text = (
        f"{html.bold('Маршрут завершён')}\n\n"
        f"Вы отметили {done} из {TOTAL} точек.\n\n"
        f"{html.quote(FINAL_SUMMARY)}"
    )
    await bot.send_message(chat_id, text, reply_markup=finale_kb())


async def send_question(bot: Bot, chat_id: int, q: int) -> None:
    item = QUIZ[q]
    text = f"{html.bold(f'Вопрос {q + 1} из {len(QUIZ)}')}\n\n{html.quote(item['q'])}"
    await bot.send_message(chat_id, text, reply_markup=quiz_kb(q, item["options"]))


@dp.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    await send_start(bot, message.chat.id)


@dp.message(Command("route"))
async def cmd_route(message: Message, bot: Bot) -> None:
    # начать или продолжить с того места, где остановились
    await send_card(bot, message.chat.id, get_user(message.chat.id)["current"])


@dp.message(Command("progress"))
async def cmd_progress(message: Message, bot: Bot) -> None:
    await send_progress(bot, message.chat.id)


@dp.message(Command("map"))
async def cmd_map(message: Message, bot: Bot) -> None:
    await send_map(bot, message.chat.id)


@dp.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(html.quote(ABOUT_TEXT))


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    """Служебная команда для демонстрации: сбросить прогресс."""
    _state.pop(str(message.chat.id), None)
    get_user(message.chat.id)
    await message.answer("Прогресс сброшен.")


@dp.callback_query(F.data == "route")
async def cb_route(cb: CallbackQuery, bot: Bot) -> None:
    await cb.answer()
    chat_id = cb.message.chat.id
    await send_card(bot, chat_id, get_user(chat_id)["current"])


@dp.callback_query(F.data == "map")
async def cb_map(cb: CallbackQuery, bot: Bot) -> None:
    await cb.answer()
    await send_map(bot, cb.message.chat.id)


@dp.callback_query(F.data == "about")
async def cb_about(cb: CallbackQuery) -> None:
    await cb.answer()
    await cb.message.answer(html.quote(ABOUT_TEXT))


def parse_idx(cb: CallbackQuery) -> int | None:
    try:
        idx = int(cb.data.split(":")[1])
    except (IndexError, ValueError):
        return None
    return idx if 0 <= idx < TOTAL else None


@dp.callback_query(F.data.startswith("visit:"))
async def cb_visit(cb: CallbackQuery) -> None:
    idx = parse_idx(cb)
    if idx is None:
        return await cb.answer()
    user = get_user(cb.message.chat.id)
    if idx not in user["visited"]:  # повторное нажатие ничего не ломает
        user["visited"].append(idx)
        save_state()
    try:
        await cb.message.edit_reply_markup(reply_markup=card_kb(idx, True))
    except TelegramBadRequest:
        pass  # «message is not modified»
    await cb.answer(f"Точка засчитана, пройдено {len(user['visited'])} из {TOTAL}")


@dp.callback_query(F.data.startswith("geo:"))
async def cb_geo(cb: CallbackQuery, bot: Bot) -> None:
    idx = parse_idx(cb)
    if idx is None:
        return await cb.answer()
    await cb.answer()
    p = POINTS[idx]
    chat_id = cb.message.chat.id
    await bot.send_location(chat_id, latitude=p["lat"], longitude=p["lon"])
    # в Яндекс.Картах порядок координат: долгота,широта
    url = f"https://yandex.ru/maps/?pt={p['lon']},{p['lat']}&z=17&l=map"
    await bot.send_message(
        chat_id,
        f"📍 {html.quote(p['title'])}",
        reply_markup=yandex_map_kb(url),
    )


@dp.callback_query(F.data.startswith("next:"))
async def cb_next(cb: CallbackQuery, bot: Bot) -> None:
    idx = parse_idx(cb)
    if idx is None:
        return await cb.answer()
    await cb.answer()
    chat_id = cb.message.chat.id
    if idx >= TOTAL - 1:  # «Дальше» на последней точке ведёт к финалу
        return await send_finale(bot, chat_id)
    await bot.send_message(chat_id, f"➡️ {html.quote(POINTS[idx]['transition'])}")
    await send_card(bot, chat_id, idx + 1)


@dp.callback_query(F.data.startswith("prev:"))
async def cb_prev(cb: CallbackQuery, bot: Bot) -> None:
    idx = parse_idx(cb)
    await cb.answer()
    if idx is None or idx == 0:
        return
    await send_card(bot, cb.message.chat.id, idx - 1)


@dp.callback_query(F.data.startswith("goto:"))
async def cb_goto(cb: CallbackQuery, bot: Bot) -> None:
    idx = parse_idx(cb)
    await cb.answer()
    if idx is not None:
        await send_card(bot, cb.message.chat.id, idx)


@dp.callback_query(F.data == "quiz_start")
async def cb_quiz_start(cb: CallbackQuery, bot: Bot) -> None:
    await cb.answer()
    chat_id = cb.message.chat.id
    user = get_user(chat_id)
    user["quiz_score"] = 0
    user["quiz_next"] = 0
    save_state()
    await send_question(bot, chat_id, 0)


@dp.callback_query(F.data.startswith("quiz:"))
async def cb_quiz_answer(cb: CallbackQuery, bot: Bot) -> None:
    try:
        _, q, a = cb.data.split(":")
        q, a = int(q), int(a)
        item = QUIZ[q]
    except (ValueError, IndexError):
        return await cb.answer()

    chat_id = cb.message.chat.id
    user = get_user(chat_id)
    if q != user["quiz_next"]:  # на вопрос уже отвечали (двойной клик)
        return await cb.answer()
    user["quiz_next"] = q + 1

    correct = a == item["correct"]
    if correct:
        user["quiz_score"] += 1
        verdict = "✅ Верно!"
    else:
        verdict = f"❌ Неверно. Правильный ответ: {item['options'][item['correct']]}"
    save_state()

    await cb.answer()
    # убираем кнопки и дописываем вердикт к вопросу
    await cb.message.edit_text(
        f"{cb.message.html_text}\n\n{html.quote(verdict)}", reply_markup=None
    )

    if q + 1 < len(QUIZ):
        await send_question(bot, chat_id, q + 1)
    else:
        await bot.send_message(
            chat_id,
            f"{html.bold('Викторина завершена')}\n"
            f"Результат: {user['quiz_score']} из {len(QUIZ)}",
        )

@dp.message()
async def fallback(message: Message) -> None:
    await message.answer("Пользуйтесь кнопками или командой /route")


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не найден. Проверьте файл .env")
    load_state()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())