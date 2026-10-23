from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _btn(text: str, data: str | None = None, url: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, url=url)


def _kb(*rows: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def main_menu_kb() -> InlineKeyboardMarkup:
    """Экран после /start."""
    return _kb(
        [_btn("Начать маршрут", "route")],
        [_btn("Карта", "map")],
        [_btn("Где поесть?", "food_map")],
        [_btn("О проекте", "about")],
    )


def card_kb(idx: int, visited: bool) -> InlineKeyboardMarkup:
    """Кнопки под карточкой остановки (два ряда)."""
    nav = []
    if idx > 0:  # на первой точке кнопки «Назад» нет
        nav.append(_btn("⬅️ Назад", f"prev:{idx}"))
    nav.append(_btn("➡️ Дальше", f"next:{idx}"))
    return _kb(
        [
            _btn("✅ Отмечено" if visited else "✅ Был здесь", f"visit:{idx}"),
            _btn("📍 На карте", f"geo:{idx}"),
        ],
        nav,
    )


def map_kb(map_url: str) -> InlineKeyboardMarkup:
    """Ссылка на карту маршрута (/map)."""
    return _kb([_btn("🗺 Открыть карту", url=map_url)])


def yandex_map_kb(url: str) -> InlineKeyboardMarkup:
    """Ссылка на одну точку в Яндекс.Картах."""
    return _kb([_btn("Открыть в Яндекс.Картах", url=url)])


def progress_kb(total: int, per_row: int = 5) -> InlineKeyboardMarkup:
    """Кнопки с номерами точек для быстрого перехода (/progress)."""
    numbers = [_btn(str(i + 1), f"goto:{i}") for i in range(total)]
    return _kb(*[numbers[i : i + per_row] for i in range(0, total, per_row)])


def finale_kb() -> InlineKeyboardMarkup:
    """Кнопка запуска викторины на финальном экране."""
    return _kb([_btn("Мини-викторина", "quiz_start")])


def quiz_kb(q: int, options: list[str]) -> InlineKeyboardMarkup:
    """Варианты ответа на вопрос викторины, по одному в ряд."""
    return _kb(*[[_btn(opt, f"quiz:{q}:{a}")] for a, opt in enumerate(options)])