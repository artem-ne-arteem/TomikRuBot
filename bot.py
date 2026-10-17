import asyncio
import calendar
import csv
import io
import json
import logging
import math
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import (
    IS_MEMBER,
    IS_NOT_MEMBER,
    ChatMemberUpdatedFilter,
    Command,
    CommandObject,
    CommandStart,
)
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BufferedInputFile,
    CallbackQuery,
    ChatMemberUpdated,
    ErrorEvent,
    FSInputFile,
    InlineKeyboardButton,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from texts import tl


# ---------- Настройки ----------
def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


load_env()
PROXY = os.getenv("PROXY") or None  # например http://127.0.0.1:8080
START_PHOTO = os.getenv("START_PHOTO", "start.png")  # картинка для /start (путь к файлу)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)  # твой Telegram ID (узнай командой /id)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Положи токен в файл .env: BOT_TOKEN=...")

# Часовой пояс (по умолчанию Москва). На Windows для ZoneInfo: pip install tzdata
try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Moscow"))
except Exception:
    logging.warning("Нет tzdata, использую UTC+3. Поставь: pip install tzdata")
    TZ = timezone(timedelta(hours=3))

PAGE_SIZE = 8  # книг на странице полки
STATUS_KEYS = ("want", "reading", "done", "dropped")
UNKNOWN_AUTHORS = {"", "—", "Автор неизвестен", "Unknown author"}
BOT_USERNAME = ""  # заполняется при старте
BOT_REF = None  # объект бота для фоновых уведомлений

# ---------- БД ----------
db = sqlite3.connect("tomik.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript(
    """
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        author TEXT,
        year INTEGER,
        status TEXT NOT NULL DEFAULT 'want',
        rating INTEGER,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        remind_time TEXT,
        last_reminded TEXT
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL,
        page INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS reading_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER,
        day TEXT NOT NULL,
        pages INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_log_user_day ON reading_log (user_id, day);
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        UNIQUE (user_id, name)
    );
    CREATE TABLE IF NOT EXISTS book_tags (
        book_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (book_id, tag_id)
    );
    CREATE TABLE IF NOT EXISTS chat_groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        lang TEXT DEFAULT 'ru',
        digest_time TEXT DEFAULT '21:00',
        last_digest TEXT
    );
    CREATE TABLE IF NOT EXISTS group_members (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (chat_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        started_ts INTEGER NOT NULL,
        ended_ts INTEGER,
        minutes INTEGER
    );
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
)


def add_cols(table: str, cols: list[tuple[str, str]]) -> None:
    have = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
    for name, ddl in cols:
        if name not in have:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


add_cols(
    "books",
    [
        ("pages", "INTEGER"),
        ("cover", "TEXT"),
        ("page", "INTEGER DEFAULT 0"),
        ("started_at", "TEXT"),
        ("finished_at", "TEXT"),
        ("genre", "TEXT"),
        ("isbn", "TEXT"),
    ],
)
add_cols(
    "users",
    [
        ("name", "TEXT"),
        ("lang", "TEXT"),
        ("goal_month", "INTEGER"),
        ("weekly_on", "INTEGER DEFAULT 0"),
        ("weekly_last", "TEXT"),
        ("source", "TEXT"),
        ("joined_at", "TEXT"),
        ("last_seen", "TEXT"),
    ],
)
add_cols("reading_log", [("minutes", "INTEGER DEFAULT 0")])
add_cols(
    "chat_groups",
    [
        ("challenge_pages", "INTEGER"),
        ("challenge_done", "TEXT"),
        ("weekly_on", "INTEGER DEFAULT 1"),
        ("weekly_last", "TEXT"),
    ],
)
db.commit()

# ---------- Состояние в памяти ----------
SEARCH: dict[int, list[dict]] = {}  # результаты последнего поиска
LAST_QUERY: dict[int, str] = {}  # последний поисковый запрос
MANUAL: dict[int, dict] = {}  # пошаговое добавление книги вручную
PENDING: dict[int, tuple[str, int]] = {}  # (prog|quote|note|tag|edit:поле, book_id)
LANG: dict[int, str] = {}  # кэш языков

pr = Router(name="private")  # личные чаты
pr.message.filter(F.chat.type == "private")
pr.callback_query.filter(F.message.chat.type == "private")
gr = Router(name="group")  # группы
gr.message.filter(F.chat.type.in_({"group", "supergroup"}))
gr.callback_query.filter(F.message.chat.type.in_({"group", "supergroup"}))
dp = Dispatcher()


# ---------- Язык и пользователи ----------
def guess_lang(code: str | None) -> str:
    return "en" if (code or "").lower().startswith("en") else "ru"


def lang_of(uid: int) -> str:
    if uid not in LANG:
        r = db.execute("SELECT lang FROM users WHERE user_id=?", (uid,)).fetchone()
        LANG[uid] = r["lang"] if r and r["lang"] else "ru"
    return LANG[uid]


def t(uid: int, key: str, **kw) -> str:
    return tl(lang_of(uid), key, **kw)


def touch_user(u) -> None:
    name = (u.full_name or u.username or str(u.id))[:60]
    today = today_str()
    row = db.execute("SELECT lang, name, last_seen FROM users WHERE user_id=?", (u.id,)).fetchone()
    if row is None:
        lang = guess_lang(u.language_code)
        db.execute(
            "INSERT INTO users (user_id, name, lang, joined_at, last_seen) VALUES (?,?,?,?,?)",
            (u.id, name, lang, now_local().isoformat(), today),
        )
    else:
        lang = row["lang"] or guess_lang(u.language_code)
        if row["lang"] != lang or row["name"] != name or row["last_seen"] != today:
            db.execute(
                "UPDATE users SET lang=?, name=?, last_seen=? WHERE user_id=?", (lang, name, today, u.id)
            )
    LANG[u.id] = lang
    db.commit()


class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not u.is_bot:
            touch_user(u)
        return await handler(event, data)


def user_name(uid: int) -> str:
    r = db.execute("SELECT name FROM users WHERE user_id=?", (uid,)).fetchone()
    return (r["name"] if r and r["name"] else str(uid))


# ---------- Время ----------
def now_local() -> datetime:
    return datetime.now(TZ)


def today_str() -> str:
    return now_local().date().isoformat()


def week_start() -> str:
    d = now_local().date()
    return (d - timedelta(days=d.weekday())).isoformat()


def month_start() -> str:
    return now_local().date().replace(day=1).isoformat()


def year_start() -> str:
    return now_local().date().replace(month=1, day=1).isoformat()


def time_passed_today(hhmm: str) -> bool:
    h, mi = map(int, hhmm.split(":"))
    n = now_local()
    return n.hour * 60 + n.minute >= h * 60 + mi


def parse_hhmm(s: str) -> str | None:
    m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", s.strip())
    return f"{int(m[1]):02d}:{m[2]}" if m else None


# ---------- Журнал чтения, серии, цели ----------
def log_reading(uid: int, pages: int, book_id: int | None = None, minutes: int = 0) -> None:
    db.execute(
        "INSERT INTO reading_log (user_id, book_id, day, pages, minutes) VALUES (?,?,?,?,?)",
        (uid, book_id, today_str(), max(0, int(pages)), max(0, int(minutes))),
    )
    db.commit()


def minutes_between(uid: int, start: str, end: str | None = None) -> int:
    end = end or today_str()
    return db.execute(
        "SELECT COALESCE(SUM(minutes), 0) m FROM reading_log WHERE user_id=? AND day>=? AND day<=?",
        (uid, start, end),
    ).fetchone()["m"]


def pages_between(uid: int, start: str, end: str | None = None) -> int:
    end = end or today_str()
    r = db.execute(
        "SELECT COALESCE(SUM(pages), 0) p FROM reading_log WHERE user_id=? AND day>=? AND day<=?",
        (uid, start, end),
    ).fetchone()
    return r["p"]


def streaks(uid: int) -> tuple[int, int]:
    """(текущая серия дней, рекорд). Серия жива, если читал сегодня или вчера."""
    days = sorted(
        {
            date.fromisoformat(r["day"])
            for r in db.execute("SELECT DISTINCT day FROM reading_log WHERE user_id=?", (uid,))
        }
    )
    if not days:
        return 0, 0
    longest = run = 1
    for a, b in zip(days, days[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        longest = max(longest, run)
    if (now_local().date() - days[-1]).days > 1:
        return 0, longest
    current = 1
    for i in range(len(days) - 1, 0, -1):
        if (days[i] - days[i - 1]).days == 1:
            current += 1
        else:
            break
    return current, longest


def read_today(uid: int) -> bool:
    return bool(
        db.execute(
            "SELECT 1 FROM reading_log WHERE user_id=? AND day=? LIMIT 1", (uid, today_str())
        ).fetchone()
    )


def bar10(done: int, total: int) -> str:
    if not total:
        return "░" * 10
    filled = max(0, min(10, round(10 * done / total)))
    return "▓" * filled + "░" * (10 - filled)


def month_done(uid: int) -> int:
    return db.execute(
        "SELECT COUNT(*) c FROM books WHERE user_id=? AND status='done' AND finished_at>=?",
        (uid, month_start()),
    ).fetchone()["c"]


def get_goal(uid: int) -> int | None:
    r = db.execute("SELECT goal_month FROM users WHERE user_id=?", (uid,)).fetchone()
    return r["goal_month"] if r and r["goal_month"] else None


def set_goal(uid: int, n: int | None) -> None:
    db.execute("UPDATE users SET goal_month=? WHERE user_id=?", (n, uid))
    db.commit()


def goal_line(uid: int) -> str:
    g = get_goal(uid)
    if not g:
        return ""
    n = month_done(uid)
    return t(uid, "goal_progress", n=n, g=g, bar=bar10(n, g))


# ---------- Поиск книг (Google Books + запасной Open Library) ----------
def has_cyrillic(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)


def stems(query: str) -> list[str]:
    out = []
    for w in re.findall(r"\w+", query.lower().replace("ё", "е")):
        if len(w) > 2:
            out.append(w[: max(4, len(w) - 2)])
    return out


def match_count(words: list[str], text: str) -> int:
    low = text.lower().replace("ё", "е")
    return sum(1 for w in words if w in low)


def rank_results(query: str, items: list[dict]) -> list[dict]:
    """Оставляем только книги, где название/автор совпадает с запросом, лучшие сверху."""
    words = stems(query)
    if not words:
        return items
    scored = [
        (
            match_count(words, it["title"]),
            match_count(words, it["title"] + " " + it["author"]),
            it,
        )
        for it in items
    ]
    need = math.ceil(len(words) * 0.6)
    good = [s for s in scored if s[1] >= need] or [s for s in scored if s[1] >= 1]
    good.sort(key=lambda s: (-s[0], -s[1]))
    return [s[2] for s in good]


def dedupe(items: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for it in items:
        k = (it["title"].lower().strip(), it["author"].lower())
        if k not in seen:
            seen[k] = dict(it)
        else:
            for f in ("cover", "pages", "genre", "year"):
                if not seen[k].get(f) and it.get(f):
                    seen[k][f] = it[f]
    return list(seen.values())


async def fetch_json(url: str, params: dict, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url, params=params, proxy=PROXY, timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    logging.warning("%s -> HTTP %s (попытка %d)", url, r.status, attempt)
                    if r.status < 500:  # 4xx повторять бессмысленно
                        return None
        except Exception:
            logging.exception("request failed: %s (попытка %d)", url, attempt)
        await asyncio.sleep(1)
    return None


async def search_google(query: str, lang: str | None = None) -> list[dict]:
    params = {
        "q": query,
        "maxResults": 20,
        "printType": "books",
        "orderBy": "relevance",
        "fields": "items(volumeInfo(title,authors,publishedDate,pageCount,categories,industryIdentifiers,imageLinks/thumbnail))",
    }
    if lang:
        params["langRestrict"] = lang
    elif has_cyrillic(query):
        params["langRestrict"] = "ru"
    if os.getenv("GOOGLE_BOOKS_KEY"):
        params["key"] = os.getenv("GOOGLE_BOOKS_KEY")
    data = await fetch_json("https://www.googleapis.com/books/v1/volumes", params)
    if not data:
        return []
    out = []
    for item in data.get("items", []):
        v = item.get("volumeInfo", {})
        if not v.get("title") or not v.get("authors"):
            continue
        date_ = v.get("publishedDate", "")[:4]
        img = (v.get("imageLinks") or {}).get("thumbnail")
        if img:
            img = img.replace("http://", "https://").replace("&edge=curl", "")
        cats = v.get("categories") or []
        isbn = None
        for ident in v.get("industryIdentifiers") or []:
            if ident.get("type") in ("ISBN_13", "ISBN_10"):
                isbn = normalize_isbn(ident.get("identifier", "")) or isbn
        out.append(
            {
                "title": v["title"],
                "author": ", ".join(v["authors"][:2]),
                "year": int(date_) if date_.isdigit() else None,
                "pages": v.get("pageCount") or None,
                "cover": img,
                "genre": (cats[0].split("/")[0].strip() or None) if cats else None,
                "isbn": isbn,
            }
        )
    return out


async def search_openlibrary(query: str) -> list[dict]:
    params = {
        "q": query,
        "limit": 20,
        "fields": "title,author_name,first_publish_year,cover_i,number_of_pages_median",
    }
    if has_cyrillic(query):
        params["language"] = "rus"
    data = await fetch_json("https://openlibrary.org/search.json", params)
    if not data:
        return []
    return [
        {
            "title": d["title"],
            "author": ", ".join(d["author_name"][:2]),
            "year": d.get("first_publish_year"),
            "pages": d.get("number_of_pages_median"),
            "cover": (
                f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg"
                if d.get("cover_i")
                else None
            ),
            "genre": None,
            "isbn": None,
        }
        for d in data.get("docs", [])
        if d.get("title") and d.get("author_name")
    ]


async def search_books(query: str) -> list[dict]:
    for name, fn in (("google", search_google), ("openlibrary", search_openlibrary)):
        results = rank_results(query, dedupe(await fn(query)))[:6]
        logging.info("search '%s': %s -> %d", query, name, len(results))
        if results:
            return results
    return []


# ---------- ISBN и штрихкоды ----------
def normalize_isbn(s: str) -> str | None:
    """ISBN-10/13 (с дефисами или без) -> ISBN-13, либо None, если контрольная цифра не сходится."""
    d = re.sub(r"[\s\-]", "", s.strip()).upper()

    def check13(core12: str) -> str:
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core12))
        return str((10 - total % 10) % 10)

    if re.fullmatch(r"97[89]\d{10}", d):
        return d if check13(d[:12]) == d[12] else None
    if re.fullmatch(r"\d{9}[\dX]", d):
        if sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d)) % 11:
            return None
        core = "978" + d[:9]
        return core + check13(core)
    return None


def looks_like_isbn(text: str) -> str | None:
    if re.fullmatch(r"[\d\-\sXx]{10,20}", text.strip()):
        return normalize_isbn(text)
    return None


def decode_barcodes(data: bytes) -> list[str]:
    """Читает штрихкоды с картинки. Нужны: pip install zxing-cpp pillow."""
    import zxingcpp
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.load()
    gray = ImageOps.autocontrast(img.convert("L"))
    variants = [img.convert("RGB"), gray]
    if max(img.size) < 1200:
        variants.append(gray.resize((img.width * 2, img.height * 2)))
    for v in variants:
        found = [r.text for r in zxingcpp.read_barcodes(v)]
        if found:
            return found
    return []


async def search_by_isbn(isbn: str) -> list[dict]:
    for fn in (search_google, search_openlibrary):
        res = dedupe(await fn(f"isbn:{isbn}"))[:3]
        if res:
            for r in res:
                r["isbn"] = isbn
            return res
    return []


async def post_json(url: str, payload: dict, headers: dict, timeout: int = 40):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                url, json=payload, headers=headers, proxy=PROXY,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                if r.status == 200:
                    return await r.json()
                logging.warning("%s -> HTTP %s", url, r.status)
    except Exception:
        logging.exception("POST failed: %s", url)
    return None


def norm_title(s: str | None) -> str:
    return re.sub(r"[\W_]+", "", (s or "").lower())


# ---------- Книги: хелперы ----------
def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def get_book(book_id: int, user_id: int):
    return db.execute(
        "SELECT * FROM books WHERE id=? AND user_id=?", (book_id, user_id)
    ).fetchone()


def author_text(uid: int, author: str | None) -> str:
    return t(uid, "unknown_author") if (author or "") in UNKNOWN_AUTHORS else escape(author)


def progress_text(uid: int, page: int, pages: int | None) -> str:
    if not pages:
        return t(uid, "pg_only", p=page)
    pct = min(100, round(page * 100 / pages))
    return t(uid, "pg_full", bar=bar10(page, pages), pct=pct, p=page, n=pages)


# ---------- Теги и полки ----------
def norm_tag(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lstrip("#").strip().lower())[:30]


def get_or_create_tag(uid: int, name: str) -> int:
    r = db.execute("SELECT id FROM tags WHERE user_id=? AND name=?", (uid, name)).fetchone()
    if r:
        return r["id"]
    cur = db.execute("INSERT INTO tags (user_id, name) VALUES (?,?)", (uid, name))
    db.commit()
    return cur.lastrowid


def book_tag_rows(book_id: int):
    return db.execute(
        "SELECT t.id, t.name FROM tags t JOIN book_tags bt ON bt.tag_id=t.id "
        "WHERE bt.book_id=? ORDER BY t.name",
        (book_id,),
    ).fetchall()


def user_tag_rows(uid: int):
    return db.execute(
        "SELECT t.id, t.name, COUNT(bt.book_id) c FROM tags t "
        "LEFT JOIN book_tags bt ON bt.tag_id=t.id WHERE t.user_id=? "
        "GROUP BY t.id ORDER BY c DESC, t.name",
        (uid,),
    ).fetchall()


def tags_view(book_id: int, uid: int):
    b = get_book(book_id, uid)
    if not b:
        return None, None
    cur = book_tag_rows(book_id)
    cur_ids = {r["id"] for r in cur}
    body = " ".join("#" + escape(r["name"]) for r in cur) if cur else t(uid, "tags_empty")
    text = t(uid, "tags_title", title=escape(b["title"])) + "\n\n" + body
    kb = InlineKeyboardBuilder()
    for r in cur:
        kb.button(text=f"✖ #{r['name']}", callback_data=f"tdel:{book_id}:{r['id']}")
    shown = 0
    for r in user_tag_rows(uid):
        if r["id"] not in cur_ids and shown < 6:
            kb.button(text=f"+ #{r['name']}", callback_data=f"tset:{book_id}:{r['id']}")
            shown += 1
    kb.adjust(2)
    kb.row(btn(t(uid, "tag_new"), f"tnew:{book_id}"))
    kb.row(btn(t(uid, "b_to_book"), f"book:{book_id}"))
    return text, kb.as_markup()


def add_book_tags(uid: int, book_id: int, raw: str) -> int:
    """Добавляет теги из строки 'фантастика, на лето'. Максимум 10 на книгу."""
    added = 0
    have = len(book_tag_rows(book_id))
    for part in re.split(r"[,\n;]+", raw):
        name = norm_tag(part)
        if not name or have >= 10:
            continue
        tid = get_or_create_tag(uid, name)
        cur = db.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?,?)", (book_id, tid)
        )
        if cur.rowcount:
            added += 1
            have += 1
    db.commit()
    return added


# ---------- Карточка книги ----------
def book_text(b) -> str:
    uid = b["user_id"]
    stars = "⭐" * b["rating"] if b["rating"] else t(uid, "unrated")
    year = f" ({b['year']})" if b["year"] else ""
    lines = [
        f"📘 <b>{escape(b['title'])}</b>{year}",
        f"✍️ {author_text(uid, b['author'])}",
    ]
    if b["genre"]:
        lines.append(f"🎭 {escape(b['genre'])}")
    lines.append(t(uid, "card_status", s=t(uid, f"st_{b['status']}")))
    if b["pages"]:
        lines.append(t(uid, "card_pages", n=b["pages"]))
    page = b["page"] or 0
    if page > 0 or b["status"] == "reading":
        lines.append("📈 " + progress_text(uid, page, b["pages"]))
    if b["started_at"]:
        lines.append(t(uid, "card_started", d=b["started_at"]))
    if b["finished_at"]:
        lines.append(t(uid, "card_finished", d=b["finished_at"]))
    names = [r["name"] for r in book_tag_rows(b["id"])]
    if names:
        lines.append("🏷 " + " ".join("#" + escape(n) for n in names))
    n_notes = db.execute("SELECT COUNT(*) c FROM notes WHERE book_id=?", (b["id"],)).fetchone()["c"]
    if n_notes:
        lines.append(t(uid, "card_notes", n=n_notes))
    lines.append(t(uid, "card_rating", r=stars))
    return "\n".join(lines)


def book_kb(b):
    uid, bid = b["user_id"], b["id"]
    kb = InlineKeyboardBuilder()
    for key in STATUS_KEYS:
        if key != b["status"]:
            kb.button(text=t(uid, f"st_{key}"), callback_data=f"st:{bid}:{key}")
    kb.adjust(2)
    kb.row(btn(t(uid, "b_progress"), f"prog:{bid}"), btn(t(uid, "b_timer"), f"tstart:{bid}"))
    kb.row(btn(t(uid, "b_notes"), f"notes:{bid}"), btn(t(uid, "b_tags"), f"tags:{bid}"))
    kb.row(btn(t(uid, "b_edit"), f"edit:{bid}"), btn(t(uid, "b_delete"), f"del:{bid}"))
    kb.row(*[btn(str(n), f"rate:{bid}:{n}") for n in range(1, 6)])
    kb.row(btn(t(uid, "b_back"), "shelf:all:0"))
    return kb.as_markup()


# ---------- Полка с фильтрами и страницами ----------
def shelf_filter(uid: int, f: str):
    if f == "all":
        return "SELECT b.* FROM books b WHERE b.user_id=?", (uid,)
    if f.startswith("t") and f[1:].isdigit():
        return (
            "SELECT b.* FROM books b JOIN book_tags bt ON bt.book_id=b.id "
            "WHERE b.user_id=? AND bt.tag_id=?",
            (uid, int(f[1:])),
        )
    return "SELECT b.* FROM books b WHERE b.user_id=? AND b.status=?", (uid, f)


def shelf_view(uid: int, f: str = "all", page: int = 0):
    where, args = shelf_filter(uid, f)
    total = db.execute(f"SELECT COUNT(*) c FROM ({where})", args).fetchone()["c"]
    n_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(0, min(page, n_pages - 1))
    rows = db.execute(
        f"{where} ORDER BY b.id DESC LIMIT ? OFFSET ?", (*args, PAGE_SIZE, page * PAGE_SIZE)
    ).fetchall()

    kb = InlineKeyboardBuilder()
    filters = {"all": t(uid, "f_all")}
    filters.update({k: t(uid, f"st_{k}") for k in STATUS_KEYS})
    for key, label in filters.items():
        kb.button(text=("• " if key == f else "") + label, callback_data=f"shelf:{key}:0")
    kb.button(text=t(uid, "f_tags"), callback_data="taglist")
    kb.adjust(2)
    for b in rows:
        label = f"{b['title'][:32]} — {(b['author'] or '')[:18]}"
        if b["status"] == "reading" and b["pages"] and b["page"]:
            label += f" · {min(100, round(b['page'] * 100 / b['pages']))}%"
        kb.row(btn(label, f"book:{b['id']}"))
    if n_pages > 1:
        nav = []
        if page > 0:
            nav.append(btn("◀️", f"shelf:{f}:{page - 1}"))
        nav.append(btn(f"{page + 1}/{n_pages}", f"shelf:{f}:{page}"))
        if page < n_pages - 1:
            nav.append(btn("▶️", f"shelf:{f}:{page + 1}"))
        kb.row(*nav)

    if f.startswith("t") and f[1:].isdigit():
        tg = db.execute("SELECT name FROM tags WHERE id=?", (int(f[1:]),)).fetchone()
        title = f"🏷 #{escape(tg['name'])}" if tg else t(uid, "shelf_title")
    elif f == "all":
        title = t(uid, "shelf_title")
    else:
        title = t(uid, f"st_{f}")
    if total:
        text = f"{title} ({total})"
    else:
        text = t(uid, "shelf_empty" if f == "all" else "shelf_empty_filter")
    return text, kb.as_markup()


# ---------- Статусы и прогресс ----------
def set_status(book_id: int, user_id: int, status: str) -> None:
    b = get_book(book_id, user_id)
    if not b or status not in STATUS_KEYS:
        return
    started, finished, page = b["started_at"], b["finished_at"], b["page"] or 0
    if status == "reading":
        started, finished = started or today_str(), None
    elif status == "done":
        started, finished = started or today_str(), finished or today_str()
        page = b["pages"] or page
    db.execute(
        "UPDATE books SET status=?, started_at=?, finished_at=?, page=? WHERE id=? AND user_id=?",
        (status, started, finished, page, book_id, user_id),
    )
    db.commit()


def set_progress(book_id: int, user_id: int, page: int, pages: int | None) -> None:
    b = get_book(book_id, user_id)
    if not b:
        return
    old = b["page"] or 0
    pages = pages or b["pages"]
    status, started, finished = b["status"], b["started_at"], b["finished_at"]
    if pages and page >= pages:
        page, status = pages, "done"
        started, finished = started or today_str(), finished or today_str()
    elif page > 0 and status != "reading":
        status, started, finished = "reading", started or today_str(), None
    db.execute(
        "UPDATE books SET page=?, pages=?, status=?, started_at=?, finished_at=? "
        "WHERE id=? AND user_id=?",
        (page, pages, status, started, finished, book_id, user_id),
    )
    db.commit()
    if page > old:  # сколько страниц прочитано сегодня — идёт в журнал, серии и лидерборды
        log_reading(user_id, page - old, book_id)


def parse_progress(text: str, pages: int | None):
    """'120' | '45%' | '120/350' -> (page, pages) или None."""
    s = text.strip().replace(" ", "")
    if m := re.fullmatch(r"(\d+)/(\d+)", s):
        return int(m[1]), int(m[2])
    if m := re.fullmatch(r"(\d+)%", s):
        if not pages:
            return None
        return round(pages * min(int(m[1]), 100) / 100), pages
    if re.fullmatch(r"\d+", s):
        return int(s), pages
    return None


# ---------- Отправка карточек (текст или фото с обложкой) ----------
async def send_card(bot: Bot, chat_id: int, b, note: str = "") -> None:
    text = (note + "\n\n" if note else "") + book_text(b)
    kb = book_kb(b)
    if b["cover"]:
        try:
            await bot.send_photo(chat_id, b["cover"], caption=text, reply_markup=kb)
            return
        except Exception:
            logging.warning("Не удалось отправить обложку: %s", b["cover"])
            db.execute("UPDATE books SET cover=NULL WHERE id=?", (b["id"],))
            db.commit()
    await bot.send_message(chat_id, text, reply_markup=kb)


async def replace_with_card(c: CallbackQuery, b, note: str = "") -> None:
    try:
        await c.message.delete()
    except Exception:
        pass
    await send_card(c.bot, c.message.chat.id, b, note)


async def update_card(c: CallbackQuery, b) -> None:
    msg, text, kb = c.message, book_text(b), book_kb(b)
    try:
        if msg.photo and b["cover"]:
            await msg.edit_caption(caption=text, reply_markup=kb)
            return
        if not msg.photo and not b["cover"]:
            await msg.edit_text(text, reply_markup=kb)
            return
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        logging.warning("edit failed: %s", e)
    await replace_with_card(c, b)


async def replace_text(c: CallbackQuery, text: str, kb) -> None:
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        try:
            await c.message.delete()
        except Exception:
            pass
        await c.bot.send_message(c.message.chat.id, text, reply_markup=kb)


# ---------- Статистика ----------
def stats_text(uid: int) -> str:
    today = now_local().date()
    counts = {
        r["status"]: r["c"]
        for r in db.execute(
            "SELECT status, COUNT(*) c FROM books WHERE user_id=? GROUP BY status", (uid,)
        )
    }
    shelf = " · ".join(f"{t(uid, f'st_{k}').split()[0]} {counts.get(k, 0)}" for k in STATUS_KEYS)
    avg = db.execute(
        "SELECT AVG(rating) a FROM books WHERE user_id=? AND rating IS NOT NULL", (uid,)
    ).fetchone()["a"]

    def done_since(start: str) -> int:
        return db.execute(
            "SELECT COUNT(*) c FROM books WHERE user_id=? AND status='done' AND finished_at>=?",
            (uid, start),
        ).fetchone()["c"]

    out = [t(uid, "st_head"), "", t(uid, "st_shelf", s=shelf)]
    out.append(t(uid, "st_avg", a=f"{avg:.1f}") if avg else t(uid, "st_avg_none"))
    out.append("")
    out.append(
        t(
            uid,
            "st_month",
            m=today.strftime("%m.%Y"),
            b=done_since(month_start()),
            p=pages_between(uid, month_start()),
        )
    )
    out.append(t(uid, "st_year", b=done_since(year_start()), p=pages_between(uid, year_start())))
    total_pages = pages_between(uid, "0000-01-01")
    last30 = pages_between(uid, (today - timedelta(days=29)).isoformat())
    out.append(t(uid, "st_total", p=total_pages, a=round(last30 / 30)))
    all_min = minutes_between(uid, "0000-01-01")
    if all_min:
        out.append(
            t(uid, "st_time", m=fmt_minutes(uid, minutes_between(uid, month_start())), a=fmt_minutes(uid, all_min))
        )
    cur, best = streaks(uid)
    out.append("")
    out.append(t(uid, "st_streak", c=cur, b=best))
    gl = goal_line(uid)
    out.append(gl if gl else t(uid, "st_goal_none"))

    authors = db.execute(
        "SELECT author, COUNT(*) c FROM books WHERE user_id=? AND author IS NOT NULL "
        "AND author NOT IN ('', '—', 'Автор неизвестен', 'Unknown author') "
        "GROUP BY author ORDER BY c DESC, author LIMIT 3",
        (uid,),
    ).fetchall()
    genres = db.execute(
        "SELECT genre, COUNT(*) c FROM books WHERE user_id=? AND genre IS NOT NULL "
        "GROUP BY genre ORDER BY c DESC, genre LIMIT 3",
        (uid,),
    ).fetchall()
    tags = [r for r in user_tag_rows(uid) if r["c"] > 0][:3]
    extra = []
    if authors:
        extra.append(t(uid, "st_authors", l=", ".join(f"{escape(r['author'])} ({r['c']})" for r in authors)))
    if genres:
        extra.append(t(uid, "st_genres", l=", ".join(f"{escape(r['genre'])} ({r['c']})" for r in genres)))
    if tags:
        extra.append(t(uid, "st_tags", l=", ".join(f"#{escape(r['name'])} ({r['c']})" for r in tags)))
    if extra:
        out.append("")
        out.extend(extra)

    per_month = {
        r["ym"]: r["c"]
        for r in db.execute(
            "SELECT substr(finished_at,1,7) ym, COUNT(*) c FROM books "
            "WHERE user_id=? AND status='done' AND finished_at IS NOT NULL GROUP BY ym",
            (uid,),
        )
    }
    if per_month:
        out.append("")
        out.append(t(uid, "st_months"))
        for j in range(5, -1, -1):
            y, m = today.year, today.month - j
            while m <= 0:
                m, y = m + 12, y - 1
            c = per_month.get(f"{y}-{m:02d}", 0)
            out.append(f"{m:02d}.{str(y)[2:]} {'▓' * min(c, 12) or '·'} {c}")
    return "\n".join(out)


# ======================================================================
#                           ЛИЧНЫЕ ЧАТЫ
# ======================================================================
_START_FILE_ID: str | None = None  # после первой отправки Telegram запоминает файл
_START_PREPARED = None  # подготовленная картинка (кэш)


def prepare_start_photo():
    """Приводит картинку к требованиям Telegram: сумма сторон <= 10000 px, пропорции не больше 20:1, вес <= 10 МБ."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    Image.MAX_IMAGE_PIXELS = None
    img = ImageOps.exif_transpose(Image.open(START_PHOTO))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        img = Image.new("RGB", rgba.size, "white")
        img.paste(rgba, mask=rgba.split()[-1])
    else:
        img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    w, h = img.size
    if max(w / h, h / w) > 19:  # слишком вытянутая: добавляем белые поля
        canvas = Image.new("RGB", (w, math.ceil(w / 19)) if w > h else (math.ceil(h / 19), h), "white")
        canvas.paste(img, ((canvas.width - w) // 2, (canvas.height - h) // 2))
        img = canvas
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return BufferedInputFile(buf.getvalue(), filename="start.jpg")


async def send_start(bot: Bot, chat_id: int, uid: int) -> None:
    """Приветствие: картинка с подписью (если файл найден), иначе просто текст."""
    global _START_FILE_ID, _START_PREPARED
    text = t(uid, "start")
    photo = _START_FILE_ID
    if not photo and os.path.isfile(START_PHOTO):
        if _START_PREPARED is None:
            try:
                _START_PREPARED = await asyncio.to_thread(prepare_start_photo)
            except Exception:
                logging.exception("не удалось обработать картинку %s", START_PHOTO)
        photo = _START_PREPARED or FSInputFile(START_PHOTO)
    if photo:
        try:
            caption = text if len(text) <= 1024 else None  # лимит подписи в Telegram
            msg = await bot.send_photo(chat_id, photo, caption=caption)
            if not _START_FILE_ID and msg.photo:
                _START_FILE_ID = msg.photo[-1].file_id
            if caption is None:
                await bot.send_message(chat_id, text)
            return
        except Exception:
            logging.exception("не удалось отправить картинку для /start: %s", START_PHOTO)
    await bot.send_message(chat_id, text)


@pr.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id
    src = re.sub(r"[^\w\-]", "", command.args or "")[:32]  # метка источника: t.me/бот?start=метка
    if src:
        db.execute(
            "UPDATE users SET source=? WHERE user_id=? AND source IS NULL AND joined_at>=?",
            (src, uid, (now_local() - timedelta(hours=1)).isoformat()),
        )
        db.commit()
    await send_start(m.bot, m.chat.id, uid)


@pr.message(Command("shelf"))
async def shelf_cmd(m: Message):
    text, kb = shelf_view(m.from_user.id)
    await m.answer(text, reply_markup=kb)


@pr.message(Command("stats"))
async def stats_cmd(m: Message):
    await m.answer(stats_text(m.from_user.id))


@pr.message(Command("cancel"))
async def cancel(m: Message):
    PENDING.pop(m.from_user.id, None)
    MANUAL.pop(m.from_user.id, None)
    await m.answer(t(m.from_user.id, "cancelled"))


# ---------- Язык ----------
def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()


@pr.message(Command("lang"))
async def lang_cmd(m: Message):
    await m.answer(t(m.from_user.id, "lang_prompt"), reply_markup=lang_kb())


@pr.callback_query(F.data.startswith("lang:"))
async def cb_lang(c: CallbackQuery):
    new = c.data.split(":")[1]
    if new not in ("ru", "en"):
        return await c.answer()
    db.execute("UPDATE users SET lang=? WHERE user_id=?", (new, c.from_user.id))
    db.commit()
    LANG[c.from_user.id] = new
    await c.message.edit_text(tl(new, "lang_set"))
    await send_start(c.bot, c.message.chat.id, c.from_user.id)
    await c.answer()


# ---------- Цель на месяц ----------
def goal_status(uid: int) -> str:
    gl = goal_line(uid)
    return gl if gl else t(uid, "goal_none")


def goal_kb(uid: int):
    kb = InlineKeyboardBuilder()
    for n in (1, 2, 4, 6, 8):
        kb.button(text=f"🎯 {n}", callback_data=f"goal:{n}")
    kb.button(text=t(uid, "goal_btn_off"), callback_data="goal:off")
    kb.adjust(5, 1)
    return kb.as_markup()


@pr.message(Command("goal"))
async def goal_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    arg = (command.args or "").strip().lower()
    if arg in ("off", "0", "-"):
        set_goal(uid, None)
        await m.answer(t(uid, "goal_off"))
    elif arg.isdigit() and 0 < int(arg) <= 100:
        set_goal(uid, int(arg))
        await m.answer(t(uid, "goal_set", n=int(arg)) + "\n\n" + goal_status(uid))
    else:
        await m.answer(goal_status(uid) + "\n\n" + t(uid, "goal_hint"), reply_markup=goal_kb(uid))


@pr.callback_query(F.data.startswith("goal:"))
async def cb_goal(c: CallbackQuery):
    uid, val = c.from_user.id, c.data.split(":")[1]
    if val == "off":
        set_goal(uid, None)
        await c.message.edit_text(t(uid, "goal_off"))
    elif val.isdigit():
        set_goal(uid, int(val))
        await c.message.edit_text(t(uid, "goal_set", n=int(val)) + "\n\n" + goal_status(uid))
    await c.answer()


# ---------- Ручной ввод прочитанных страниц ----------
async def read_impl(m: Message, command: CommandObject, group: bool) -> None:
    uid = m.from_user.id
    lang = group_lang(m.chat.id) if group else lang_of(uid)
    arg = (command.args or "").strip()
    if not arg.isdigit() or not (0 < int(arg) <= 3000):
        await m.answer(tl(lang, "read_usage"))
        return
    n = int(arg)
    if group:
        ensure_group(m.chat, guess_lang(m.from_user.language_code))
        join_group(m.chat.id, uid)
    log_reading(uid, n)
    total = pages_between(uid, today_str(), today_str())
    cur, _ = streaks(uid)
    if group:
        text = tl(lang, "g_read_ok", name=escape(user_name(uid)), n=n, total=total)
    else:
        text = tl(lang, "read_ok", n=n, total=total)
    if cur:
        text += "\n" + tl(lang, "streak_line", n=cur)
    await m.answer(text)
    await check_challenges(m.bot, uid)


@pr.message(Command("read"))
async def read_cmd(m: Message, command: CommandObject):
    await read_impl(m, command, group=False)


# ---------- Напоминания ----------
def remind_kb(uid: int):
    kb = InlineKeyboardBuilder()
    for tm in ("08:00", "12:00", "18:00", "21:00"):
        kb.button(text=f"🔔 {tm}", callback_data=f"rem:{tm}")
    kb.button(text=t(uid, "rem_btn_off"), callback_data="rem:off")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def save_remind(user_id: int, tm: str | None) -> None:
    last = today_str() if (tm and time_passed_today(tm)) else None  # прошло — начнём завтра
    db.execute(
        "UPDATE users SET remind_time=?, last_reminded=? WHERE user_id=?", (tm, last, user_id)
    )
    db.commit()


@pr.message(Command("remind"))
async def remind(m: Message, command: CommandObject):
    uid = m.from_user.id
    if command.args:
        tm = parse_hhmm(command.args)
        if not tm:
            await m.answer(t(uid, "rem_usage"))
            return
        save_remind(uid, tm)
        await m.answer(t(uid, "rem_set", t=tm))
        return
    row = db.execute("SELECT remind_time FROM users WHERE user_id=?", (uid,)).fetchone()
    cur = row["remind_time"] if row and row["remind_time"] else None
    head = t(uid, "rem_cur", t=cur) if cur else t(uid, "rem_off_now")
    await m.answer(head + "\n\n" + t(uid, "rem_pick"), reply_markup=remind_kb(uid))


@pr.callback_query(F.data.startswith("rem:"))
async def cb_remind(c: CallbackQuery):
    uid, val = c.from_user.id, c.data.split(":", 1)[1]
    if val == "off":
        save_remind(uid, None)
        await c.message.edit_text(t(uid, "rem_off"))
    else:
        tm = parse_hhmm(val)
        if tm:
            save_remind(uid, tm)
            await c.message.edit_text(t(uid, "rem_set", t=tm))
    await c.answer()


async def send_reminder(bot: Bot, uid: int) -> None:
    rows = db.execute(
        "SELECT * FROM books WHERE user_id=? AND status='reading' ORDER BY id DESC LIMIT 3",
        (uid,),
    ).fetchall()
    cur, _ = streaks(uid)
    streak = ("\n\n" + t(uid, "rem_streak", n=cur)) if (cur and not read_today(uid)) else ""
    if rows:
        kb = InlineKeyboardBuilder()
        lines = [t(uid, "rem_title"), "", t(uid, "rem_in_progress")]
        for b in rows:
            lines.append(f"• {escape(b['title'])} — {progress_text(uid, b['page'] or 0, b['pages'])}")
            kb.row(btn(f"📈 {b['title'][:40]}", f"prog:{b['id']}"))
        await bot.send_message(uid, "\n".join(lines) + streak, reply_markup=kb.as_markup())
    else:
        await bot.send_message(uid, t(uid, "rem_title") + "\n\n" + t(uid, "rem_empty") + streak)


# ---------- Добавление книги вручную ----------
def manual_kb(uid: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(uid, "manual_btn"), callback_data="manual:start")
    return kb.as_markup()


def start_manual(uid: int, title: str | None = None) -> None:
    PENDING.pop(uid, None)
    MANUAL[uid] = {"step": "author" if title else "title", "title": title}


async def handle_manual(m: Message) -> None:
    uid = m.from_user.id
    d = MANUAL[uid]
    txt = m.text.strip()
    skip = txt in ("-", "—")
    step = d["step"]
    if step == "title":
        if skip:
            await m.answer(t(uid, "m_title"))
            return
        d["title"], d["step"] = txt[:200], "author"
    elif step == "author":
        d["author"], d["step"] = ("—" if skip else txt[:120]), "pages"
    elif step == "pages":
        if skip:
            d["pages"] = None
        elif txt.isdigit() and 0 < int(txt) <= 10000:
            d["pages"] = int(txt)
        else:
            await m.answer(t(uid, "m_pages_err"))
            return
        d["step"] = "year"
    elif step == "year":
        if skip:
            year = None
        elif txt.isdigit() and 1000 <= int(txt) <= 2100:
            year = int(txt)
        else:
            await m.answer(t(uid, "m_year_err"))
            return
        MANUAL.pop(uid, None)
        cur = db.execute(
            "INSERT INTO books (user_id, title, author, year, pages) VALUES (?,?,?,?,?)",
            (uid, d["title"], d.get("author") or "—", year, d.get("pages")),
        )
        db.commit()
        await send_card(m.bot, m.chat.id, get_book(cur.lastrowid, uid), t(uid, "card_added"))
        return
    await m.answer(t(uid, f"m_{d['step']}"))


@pr.message(Command("add"))
async def add_manual(m: Message):
    uid = m.from_user.id
    start_manual(uid)
    await m.answer(t(uid, "m_start_blank") + "\n\n" + t(uid, "m_title"))


@pr.callback_query(F.data == "manual:start")
async def cb_manual(c: CallbackQuery):
    uid = c.from_user.id
    q = LAST_QUERY.get(uid)
    start_manual(uid, q[:200] if q else None)
    if q:
        text = t(uid, "m_start_query", q=escape(q)) + "\n\n" + t(uid, "m_author")
    else:
        text = t(uid, "m_start_blank") + "\n\n" + t(uid, "m_title")
    await c.message.answer(text)
    await c.answer()


# ---------- Текст: ввод по режимам или поиск ----------
async def handle_progress(m: Message) -> bool:
    uid = m.from_user.id
    b = get_book(PENDING[uid][1], uid)
    if not b:
        PENDING.pop(uid, None)
        return False
    if m.text.strip() in ("-", "—"):
        PENDING.pop(uid, None)
        await m.answer(t(uid, "skipped"))
        return True
    if m.text.strip().endswith("%") and not b["pages"]:
        await m.answer(t(uid, "prog_need_pages"))
        return True
    parsed = parse_progress(m.text, b["pages"])
    if not parsed:
        PENDING.pop(uid, None)  # это не число: считаем новым поиском
        return False
    page, pages = parsed
    PENDING.pop(uid, None)
    set_progress(b["id"], uid, page, pages)
    nb = get_book(b["id"], uid)
    note = t(uid, "book_done") if nb["status"] == "done" else t(uid, "prog_updated")
    cur, _ = streaks(uid)
    if cur:
        note += "\n" + t(uid, "streak_line", n=cur)
    if nb["status"] == "done":
        gl = goal_line(uid)
        if gl:
            note += "\n" + gl
    await send_card(m.bot, m.chat.id, nb, note)
    await check_challenges(m.bot, uid)
    return True


@pr.message(F.text & ~F.text.startswith("/"))
async def on_text(m: Message):
    uid = m.from_user.id
    if uid in MANUAL:
        await handle_manual(m)
        return
    if uid in PENDING:
        kind = PENDING[uid][0]
        if kind == "prog":
            if await handle_progress(m):
                return
        elif kind in ("quote", "note"):
            await handle_note(m)
            return
        elif kind == "tag":
            await handle_tag_input(m)
            return
        elif kind.startswith("edit:"):
            await handle_edit(m)
            return
    LAST_QUERY[uid] = m.text.strip()
    msg = await m.answer(t(uid, "searching"))
    isbn = looks_like_isbn(m.text)
    if isbn:
        LAST_QUERY[uid] = ""
        results = await search_by_isbn(isbn)
        if not results:
            await msg.edit_text(t(uid, "nothing_found_isbn", isbn=isbn), reply_markup=manual_kb(uid))
            return
    else:
        results = await search_books(m.text.strip())
        if not results:
            await msg.edit_text(t(uid, "nothing_found"), reply_markup=manual_kb(uid))
            return
    await show_results(msg, uid, results)


@pr.message(F.photo)
async def on_photo(m: Message):
    uid = m.from_user.id
    p = PENDING.get(uid)
    if not p or p[0] != "edit:cover":
        await scan_barcode(m, m.photo[-1].file_id)
        return
    PENDING.pop(uid, None)
    db.execute(
        "UPDATE books SET cover=? WHERE id=? AND user_id=?", (m.photo[-1].file_id, p[1], uid)
    )
    db.commit()
    b = get_book(p[1], uid)
    if b:
        await send_card(m.bot, m.chat.id, b, t(uid, "saved"))


# ---------- Основные callbacks ----------
@pr.callback_query(F.data.startswith("add:"))
async def cb_add(c: CallbackQuery):
    uid = c.from_user.id
    idx = int(c.data.split(":")[1])
    results = SEARCH.get(uid, [])
    if idx >= len(results):
        await c.answer(t(uid, "search_expired"), show_alert=True)
        return
    r = results[idx]
    cur = db.execute(
        "INSERT INTO books (user_id, title, author, year, pages, cover, genre, isbn) VALUES (?,?,?,?,?,?,?,?)",
        (uid, r["title"], r["author"], r["year"], r.get("pages"), r.get("cover"), r.get("genre"), r.get("isbn")),
    )
    db.commit()
    await replace_with_card(c, get_book(cur.lastrowid, uid), t(uid, "card_added"))
    await c.answer()


@pr.callback_query(F.data.startswith("shelf:"))
async def cb_shelf(c: CallbackQuery):
    parts = c.data.split(":")
    f = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    text, kb = shelf_view(c.from_user.id, f, page)
    await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("book:"))
async def cb_book(c: CallbackQuery):
    uid = c.from_user.id
    b = get_book(int(c.data.split(":")[1]), uid)
    if not b:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    await replace_with_card(c, b)
    await c.answer()


@pr.callback_query(F.data.startswith("st:"))
async def cb_status(c: CallbackQuery):
    uid = c.from_user.id
    _, book_id, status = c.data.split(":")
    set_status(int(book_id), uid, status)
    b = get_book(int(book_id), uid)
    if b:
        await update_card(c, b)
    popup = (goal_line(uid) if status == "done" else "") or t(uid, "status_updated")
    await c.answer(popup)


@pr.callback_query(F.data.startswith("rate:"))
async def cb_rate(c: CallbackQuery):
    uid = c.from_user.id
    _, book_id, n = c.data.split(":")
    db.execute(
        "UPDATE books SET rating=? WHERE id=? AND user_id=?", (int(n), int(book_id), uid)
    )
    db.commit()
    b = get_book(int(book_id), uid)
    if b:
        await update_card(c, b)
    await c.answer(t(uid, "rating_saved"))


@pr.callback_query(F.data.startswith("prog:"))
async def cb_prog(c: CallbackQuery):
    uid = c.from_user.id
    book_id = int(c.data.split(":")[1])
    b = get_book(book_id, uid)
    if not b:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    MANUAL.pop(uid, None)
    PENDING[uid] = ("prog", book_id)
    key = "prog_prompt" if b["pages"] else "prog_prompt_nopages"
    await c.message.answer(t(uid, key, title=escape(b["title"])))
    await c.answer()


@pr.callback_query(F.data.startswith("del:"))
async def cb_delete(c: CallbackQuery):
    uid = c.from_user.id
    bid = int(c.data.split(":")[1])
    db.execute("DELETE FROM notes WHERE book_id=? AND user_id=?", (bid, uid))
    db.execute(
        "DELETE FROM book_tags WHERE book_id IN (SELECT id FROM books WHERE id=? AND user_id=?)",
        (bid, uid),
    )
    db.execute("DELETE FROM books WHERE id=? AND user_id=?", (bid, uid))
    db.commit()
    text, kb = shelf_view(uid)
    await replace_text(c, t(uid, "deleted") + "\n\n" + text, kb)
    await c.answer()


# ---------- Заметки и цитаты ----------
PAGE_RE = re.compile(
    r"^(.*?)[\s,;(\[—-]+(?:стр\.?|с\.?|p\.?|pg\.?|page)\s*(\d{1,5})\)?\]?\s*$", re.S | re.I
)


def split_page(text: str):
    """'Цитата, стр. 45' -> ('Цитата', 45)."""
    m = PAGE_RE.match(text.strip())
    if m and m[1].strip():
        return m[1].strip(), int(m[2])
    return text.strip(), None


def notes_view(book_id: int, uid: int):
    b = get_book(book_id, uid)
    if not b:
        return None, None
    total = db.execute(
        "SELECT COUNT(*) c FROM notes WHERE book_id=? AND user_id=?", (book_id, uid)
    ).fetchone()["c"]
    rows = db.execute(
        "SELECT * FROM notes WHERE book_id=? AND user_id=? ORDER BY id DESC LIMIT 8",
        (book_id, uid),
    ).fetchall()[::-1]
    lines = [t(uid, "notes_title", title=escape(b["title"])), ""]
    if not rows:
        lines.append(t(uid, "notes_empty"))
    for i, n in enumerate(rows, 1):
        txt = escape(n["text"][:300]) + ("…" if len(n["text"]) > 300 else "")
        if n["kind"] == "quote":
            page = t(uid, "note_page", p=n["page"]) if n["page"] else ""
            lines.append(f"{i}. 💬 «{txt}»{page}")
        else:
            lines.append(f"{i}. ✏️ {txt}")
    if total > len(rows):
        lines.append("\n" + t(uid, "notes_more", k=len(rows), n=total))
    kb = InlineKeyboardBuilder()
    kb.row(btn(t(uid, "note_add_quote"), f"nadd:quote:{book_id}"), btn(t(uid, "note_add_note"), f"nadd:note:{book_id}"))
    if rows:
        kb.row(*[btn(f"🗑 {i}", f"ndel:{n['id']}") for i, n in enumerate(rows, 1)])
    kb.row(btn(t(uid, "b_to_book"), f"book:{book_id}"))
    return "\n".join(lines), kb.as_markup()


def build_export(uid: int):
    rows = db.execute(
        "SELECT n.*, b.title, b.author FROM notes n JOIN books b ON b.id = n.book_id "
        "WHERE n.user_id=? ORDER BY b.id, n.id",
        (uid,),
    ).fetchall()
    if not rows:
        return None
    out = [t(uid, "export_head")]
    cur = None
    for r in rows:
        if r["book_id"] != cur:
            cur = r["book_id"]
            author = t(uid, "unknown_author") if (r["author"] or "") in UNKNOWN_AUTHORS else r["author"]
            out.append(f"\n## {r['title']} — {author}\n")
        if r["kind"] == "quote":
            page = t(uid, "note_page", p=r["page"]) if r["page"] else ""
            out.append("> " + r["text"].replace("\n", "\n> ") + page + "\n")
        else:
            out.append("- " + r["text"].replace("\n", "\n  ") + "\n")
    return "\n".join(out) + "\n"


async def handle_note(m: Message) -> None:
    uid = m.from_user.id
    kind, book_id = PENDING.pop(uid)
    if not get_book(book_id, uid):
        await m.answer(t(uid, "not_found"))
        return
    text, page = m.text.strip()[:1500], None
    if kind == "quote":
        text, page = split_page(text)
    db.execute(
        "INSERT INTO notes (user_id, book_id, kind, text, page) VALUES (?,?,?,?,?)",
        (uid, book_id, kind, text, page),
    )
    db.commit()
    view, kb = notes_view(book_id, uid)
    await m.answer(t(uid, "saved") + "\n\n" + view, reply_markup=kb)


@pr.callback_query(F.data.startswith("notes:"))
async def cb_notes(c: CallbackQuery):
    uid = c.from_user.id
    text, kb = notes_view(int(c.data.split(":")[1]), uid)
    if not text:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("nadd:"))
async def cb_nadd(c: CallbackQuery):
    uid = c.from_user.id
    _, kind, book_id = c.data.split(":")
    if kind not in ("quote", "note") or not get_book(int(book_id), uid):
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    MANUAL.pop(uid, None)
    PENDING[uid] = (kind, int(book_id))
    await c.message.answer(t(uid, "note_hint_quote" if kind == "quote" else "note_hint_note"))
    await c.answer()


@pr.callback_query(F.data.startswith("ndel:"))
async def cb_ndel(c: CallbackQuery):
    uid = c.from_user.id
    n = db.execute(
        "SELECT * FROM notes WHERE id=? AND user_id=?", (int(c.data.split(":")[1]), uid)
    ).fetchone()
    if n:
        db.execute("DELETE FROM notes WHERE id=?", (n["id"],))
        db.commit()
        text, kb = notes_view(n["book_id"], uid)
        await replace_text(c, text, kb)
    await c.answer(t(uid, "deleted_short"))


@pr.message(Command("export"))
async def export_notes(m: Message):
    uid = m.from_user.id
    md = build_export(uid)
    if not md:
        await m.answer(t(uid, "export_empty"))
        return
    await m.answer_document(
        BufferedInputFile(md.encode("utf-8"), filename="tomik-notes.md"),
        caption=t(uid, "export_caption"),
    )


# ---------- Теги ----------
async def handle_tag_input(m: Message) -> None:
    uid = m.from_user.id
    _, book_id = PENDING.pop(uid)
    if not get_book(book_id, uid):
        await m.answer(t(uid, "not_found"))
        return
    add_book_tags(uid, book_id, m.text)
    text, kb = tags_view(book_id, uid)
    await m.answer(t(uid, "saved") + "\n\n" + text, reply_markup=kb)


@pr.callback_query(F.data.startswith("tags:"))
async def cb_tags(c: CallbackQuery):
    uid = c.from_user.id
    text, kb = tags_view(int(c.data.split(":")[1]), uid)
    if not text:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("tdel:"))
async def cb_tdel(c: CallbackQuery):
    uid = c.from_user.id
    _, book_id, tag_id = c.data.split(":")
    if get_book(int(book_id), uid):
        db.execute("DELETE FROM book_tags WHERE book_id=? AND tag_id=?", (int(book_id), int(tag_id)))
        db.commit()
        text, kb = tags_view(int(book_id), uid)
        await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("tset:"))
async def cb_tset(c: CallbackQuery):
    uid = c.from_user.id
    _, book_id, tag_id = c.data.split(":")
    tg = db.execute("SELECT id FROM tags WHERE id=? AND user_id=?", (int(tag_id), uid)).fetchone()
    if tg and get_book(int(book_id), uid):
        if len(book_tag_rows(int(book_id))) >= 10:
            await c.answer(t(uid, "tag_limit"), show_alert=True)
            return
        db.execute("INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?,?)", (int(book_id), tg["id"]))
        db.commit()
        text, kb = tags_view(int(book_id), uid)
        await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("tnew:"))
async def cb_tnew(c: CallbackQuery):
    uid = c.from_user.id
    book_id = int(c.data.split(":")[1])
    if not get_book(book_id, uid):
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    MANUAL.pop(uid, None)
    PENDING[uid] = ("tag", book_id)
    await c.message.answer(t(uid, "tag_prompt"))
    await c.answer()


@pr.callback_query(F.data == "taglist")
async def cb_taglist(c: CallbackQuery):
    uid = c.from_user.id
    rows = [r for r in user_tag_rows(uid) if r["c"] > 0]
    if not rows:
        await c.answer(t(uid, "tags_none"), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for r in rows[:30]:
        kb.button(text=f"#{r['name']} ({r['c']})", callback_data=f"shelf:t{r['id']}:0")
    kb.adjust(2)
    kb.row(btn(t(uid, "b_back"), "shelf:all:0"))
    await replace_text(c, t(uid, "taglist_title"), kb.as_markup())
    await c.answer()


# ---------- Редактирование книги ----------
EDIT_FIELDS = ("title", "author", "pages", "year", "cover")


@pr.callback_query(F.data.startswith("edit:"))
async def cb_edit(c: CallbackQuery):
    uid = c.from_user.id
    book_id = int(c.data.split(":")[1])
    b = get_book(book_id, uid)
    if not b:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for f in EDIT_FIELDS:
        kb.button(text=t(uid, f"ef_{f}"), callback_data=f"ef:{f}:{book_id}")
    kb.adjust(2)
    kb.row(btn(t(uid, "b_to_book"), f"book:{book_id}"))
    await replace_text(c, t(uid, "edit_title", title=escape(b["title"])), kb.as_markup())
    await c.answer()


@pr.callback_query(F.data.startswith("ef:"))
async def cb_ef(c: CallbackQuery):
    uid = c.from_user.id
    _, field, book_id = c.data.split(":")
    if field not in EDIT_FIELDS or not get_book(int(book_id), uid):
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    MANUAL.pop(uid, None)
    PENDING[uid] = (f"edit:{field}", int(book_id))
    await c.message.answer(t(uid, f"ep_{field}"))
    await c.answer()


async def handle_edit(m: Message) -> None:
    uid = m.from_user.id
    kind, book_id = PENDING[uid]
    field = kind.split(":", 1)[1]
    b = get_book(book_id, uid)
    if not b:
        PENDING.pop(uid, None)
        await m.answer(t(uid, "not_found"))
        return
    v = m.text.strip()
    skip = v in ("-", "—")
    upd: dict[str, object] = {}
    if field == "title":
        if skip or not v:
            await m.answer(t(uid, "ep_title"))
            return
        upd["title"] = v[:200]
    elif field == "author":
        upd["author"] = "—" if skip else v[:120]
    elif field == "pages":
        if skip:
            upd["pages"] = None
        elif v.isdigit() and 0 < int(v) <= 10000:
            upd["pages"] = int(v)
            if (b["page"] or 0) > int(v):
                upd["page"] = int(v)
        else:
            await m.answer(t(uid, "m_pages_err"))
            return
    elif field == "year":
        if skip:
            upd["year"] = None
        elif v.isdigit() and 1000 <= int(v) <= 2100:
            upd["year"] = int(v)
        else:
            await m.answer(t(uid, "m_year_err"))
            return
    elif field == "cover":
        if not v.lower().startswith("http"):
            await m.answer(t(uid, "ep_cover"))
            return
        upd["cover"] = v
    PENDING.pop(uid, None)
    sets = ", ".join(f"{k}=?" for k in upd)  # имена колонок — из фиксированного набора выше
    db.execute(f"UPDATE books SET {sets} WHERE id=? AND user_id=?", (*upd.values(), book_id, uid))
    db.commit()
    await send_card(m.bot, m.chat.id, get_book(book_id, uid), t(uid, "saved"))


# ======================================================================
#     ШТРИХКОДЫ, ТАЙМЕР, РЕКОМЕНДАЦИИ, НЕДЕЛЯ, ИМПОРТ (личные чаты)
# ======================================================================
async def show_results(msg: Message, uid: int, results: list[dict]) -> None:
    SEARCH[uid] = results
    kb = InlineKeyboardBuilder()
    for i, r in enumerate(results):
        year = f", {r['year']}" if r.get("year") else ""
        kb.button(text=f"{r['title'][:35]} — {r['author'][:20]}{year}", callback_data=f"add:{i}")
    kb.button(text=t(uid, "manual_btn_list"), callback_data="manual:start")
    kb.adjust(1)
    await msg.edit_text(t(uid, "pick_book"), reply_markup=kb.as_markup())


# ---------- Фото штрихкода ----------
async def scan_barcode(m: Message, file_id: str) -> None:
    uid = m.from_user.id
    msg = await m.answer(t(uid, "scan_working"))
    try:
        buf = await m.bot.download(file_id)
        codes = await asyncio.to_thread(decode_barcodes, buf.read())
    except ImportError:
        await msg.edit_text(t(uid, "scan_nolib"))
        return
    except Exception:
        logging.exception("barcode scan failed")
        await msg.edit_text(t(uid, "scan_fail"))
        return
    isbn = next((i for i in map(normalize_isbn, codes) if i), None)
    if not isbn:
        await msg.edit_text(t(uid, "scan_fail"))
        return
    LAST_QUERY[uid] = ""
    results = await search_by_isbn(isbn)
    if not results:
        await msg.edit_text(t(uid, "nothing_found_isbn", isbn=isbn), reply_markup=manual_kb(uid))
        return
    await show_results(msg, uid, results)


@pr.message(F.document)
async def on_document(m: Message):
    uid = m.from_user.id
    doc = m.document
    name = (doc.file_name or "").lower()
    mime = (doc.mime_type or "").lower()
    if name.endswith(".csv") or "csv" in mime:
        await import_csv(m)
    elif mime.startswith("image/"):
        await scan_barcode(m, doc.file_id)
    else:
        await m.answer(t(uid, "doc_unknown"))


# ---------- Таймер чтения ----------
SESSION_MAX_MIN = 240


def active_session(uid: int):
    return db.execute(
        "SELECT * FROM sessions WHERE user_id=? AND ended_ts IS NULL ORDER BY id DESC LIMIT 1",
        (uid,),
    ).fetchone()


def fmt_minutes(uid: int, mins: int) -> str:
    h, mi = divmod(int(mins), 60)
    return t(uid, "fmt_hm", h=h, m=mi) if h else t(uid, "fmt_m", m=mi)


def session_view(uid: int, s, note: str = ""):
    b = get_book(s["book_id"], uid)
    elapsed = int((time.time() - s["started_ts"]) // 60)
    since = datetime.fromtimestamp(s["started_ts"], TZ).strftime("%H:%M")
    text = t(
        uid, "timer_status",
        title=escape(b["title"]) if b else "?", since=since, m=fmt_minutes(uid, elapsed),
    )
    kb = InlineKeyboardBuilder()
    kb.row(btn(t(uid, "timer_btn_stop"), f"tstop:{s['id']}"), btn(t(uid, "timer_btn_refresh"), f"tshow:{s['id']}"))
    kb.row(btn(t(uid, "timer_btn_cancel"), f"tcancel:{s['id']}"))
    return (note + "\n\n" if note else "") + text, kb.as_markup()


@pr.message(Command("timer"))
async def timer_cmd(m: Message):
    uid = m.from_user.id
    s = active_session(uid)
    if s:
        text, kb = session_view(uid, s)
        await m.answer(text, reply_markup=kb)
        return
    rows = db.execute(
        "SELECT * FROM books WHERE user_id=? AND status='reading' ORDER BY id DESC LIMIT 8", (uid,)
    ).fetchall()
    if not rows:
        await m.answer(t(uid, "timer_none"))
        return
    kb = InlineKeyboardBuilder()
    for b in rows:
        kb.row(btn(f"▶️ {b['title'][:40]}", f"tstart:{b['id']}"))
    await m.answer(t(uid, "timer_pick"), reply_markup=kb.as_markup())


@pr.callback_query(F.data.startswith("tstart:"))
async def cb_tstart(c: CallbackQuery):
    uid = c.from_user.id
    book_id = int(c.data.split(":")[1])
    b = get_book(book_id, uid)
    if not b:
        await c.answer(t(uid, "not_found"), show_alert=True)
        return
    s, note = active_session(uid), ""
    if s:
        note = t(uid, "timer_already")
    else:
        if b["status"] != "reading":
            set_status(book_id, uid, "reading")
        db.execute(
            "INSERT INTO sessions (user_id, book_id, started_ts) VALUES (?,?,?)",
            (uid, book_id, int(time.time())),
        )
        db.commit()
        s = active_session(uid)
    text, kb = session_view(uid, s, note)
    await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("tshow:"))
async def cb_tshow(c: CallbackQuery):
    uid = c.from_user.id
    s = db.execute(
        "SELECT * FROM sessions WHERE id=? AND user_id=? AND ended_ts IS NULL",
        (int(c.data.split(":")[1]), uid),
    ).fetchone()
    if not s:
        await c.answer(t(uid, "timer_gone"), show_alert=True)
        return
    text, kb = session_view(uid, s)
    await replace_text(c, text, kb)
    await c.answer()


@pr.callback_query(F.data.startswith("tstop:"))
async def cb_tstop(c: CallbackQuery):
    uid = c.from_user.id
    s = db.execute(
        "SELECT * FROM sessions WHERE id=? AND user_id=?", (int(c.data.split(":")[1]), uid)
    ).fetchone()
    if not s or s["ended_ts"]:
        await c.answer(t(uid, "timer_gone"), show_alert=True)
        return
    elapsed = max(1, round((time.time() - s["started_ts"]) / 60))
    minutes = min(elapsed, SESSION_MAX_MIN)
    db.execute(
        "UPDATE sessions SET ended_ts=?, minutes=? WHERE id=?", (int(time.time()), minutes, s["id"])
    )
    db.commit()
    log_reading(uid, 0, s["book_id"], minutes)
    text = t(uid, "timer_done", m=fmt_minutes(uid, minutes))
    if elapsed > SESSION_MAX_MIN:
        text += "\n" + t(uid, "timer_capped")
    b = get_book(s["book_id"], uid)
    if b:
        MANUAL.pop(uid, None)
        PENDING[uid] = ("prog", b["id"])
        key = "prog_prompt" if b["pages"] else "prog_prompt_nopages"
        text += "\n\n" + t(uid, key, title=escape(b["title"])) + "\n" + t(uid, "timer_skip_hint")
    await replace_text(c, text, None)
    await c.answer()


@pr.callback_query(F.data.startswith("tcancel:"))
async def cb_tcancel(c: CallbackQuery):
    uid = c.from_user.id
    db.execute(
        "DELETE FROM sessions WHERE id=? AND user_id=? AND ended_ts IS NULL",
        (int(c.data.split(":")[1]), uid),
    )
    db.commit()
    await replace_text(c, t(uid, "timer_cancelled"), None)
    await c.answer()


# ---------- Рекомендации ----------
RECS_CACHE: dict[int, tuple[float, list[dict], str]] = {}


async def recs_google(uid: int) -> list[dict]:
    """Книги тех же авторов и жанров, которые тебе нравятся (без дублей с твоей полкой)."""
    books = db.execute("SELECT * FROM books WHERE user_id=?", (uid,)).fetchall()
    liked = [b for b in books if (b["rating"] or 0) >= 4] or [b for b in books if b["status"] == "done"]
    if not liked:
        return []
    authors = Counter(b["author"] for b in liked if (b["author"] or "") not in UNKNOWN_AUTHORS)
    genres = Counter(b["genre"] for b in books if b["genre"])
    lang = "ru" if lang_of(uid) == "ru" else "en"
    jobs = [("author", a, search_google(f'inauthor:"{a}"')) for a, _ in authors.most_common(3)]
    jobs += [("genre", g, search_google(f"subject:{g}", lang=lang)) for g, _ in genres.most_common(2)]
    if not jobs:
        return []
    results = await asyncio.gather(*(j[2] for j in jobs), return_exceptions=True)
    have = {norm_title(b["title"]) for b in books}
    picked, seen = [], set()
    for (kind, label, _), res in zip(jobs, results):
        if isinstance(res, Exception):
            continue
        taken = 0
        for r in sorted(dedupe(res), key=lambda x: not x.get("cover")):  # с обложкой — выше
            nt = norm_title(r["title"])
            if nt in have or nt in seen:
                continue
            if kind == "author" and label.lower() not in r["author"].lower():
                continue
            seen.add(nt)
            r = dict(r)
            r["why"] = t(uid, "recs_why_author", a=label) if kind == "author" else t(uid, "recs_why_genre", g=label)
            picked.append(r)
            taken += 1
            if taken >= 2:
                break
    return picked[:6]


async def recs_ai(uid: int) -> list[dict]:
    """Подборка от Claude (нужен ANTHROPIC_API_KEY в .env). Книги потом находим в Google Books."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return []
    books = db.execute(
        "SELECT title, author, rating, status FROM books WHERE user_id=? "
        "ORDER BY (rating IS NULL), rating DESC, id DESC LIMIT 30",
        (uid,),
    ).fetchall()
    if len(books) < 3:
        return []
    lines = "\n".join(
        f"- {b['title']} — {b['author']}" + (f" ({b['rating']}/5)" if b["rating"] else "") + f" [{b['status']}]"
        for b in books
    )
    lang_name = "Russian" if lang_of(uid) == "ru" else "English"
    prompt = (
        "You are a thoughtful book recommender. Here is a reader's shelf "
        "(ratings out of 5, higher means they liked it more):\n"
        f"{lines}\n\nRecommend 5 books they have NOT listed and would likely enjoy. "
        "Reply with ONLY a JSON array of objects with keys \"title\", \"author\" and \"why\" "
        f"(one short sentence in {lang_name}, no markdown)."
    )
    data = await post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            "max_tokens": 900,
            "messages": [{"role": "user", "content": prompt}],
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    if not data:
        return []
    try:
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        items = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
    except Exception:
        logging.exception("не разобрал ответ ИИ")
        return []
    have = {norm_title(b["title"]) for b in books}

    async def resolve(item):
        found = await search_books(f"{item.get('title', '')} {item.get('author', '')}")
        if not found or norm_title(found[0]["title"]) in have:
            return None
        r = dict(found[0])
        r["why"] = str(item.get("why") or "")[:200]
        return r

    resolved = await asyncio.gather(*(resolve(i) for i in items[:5] if isinstance(i, dict)))
    return [r for r in resolved if r]


@pr.message(Command("recs"))
async def recs_cmd(m: Message):
    uid = m.from_user.id
    msg = await m.answer(t(uid, "recs_wait"))
    cached = RECS_CACHE.get(uid)
    if cached and time.time() - cached[0] < 600:
        _, results, source = cached
    else:
        results, source = [], "google"
        try:
            results = await recs_ai(uid)
            source = "ai"
            if not results:
                results, source = await recs_google(uid), "google"
        except Exception:
            logging.exception("recs failed")
            await msg.edit_text(t(uid, "recs_fail"))
            return
        if results:
            RECS_CACHE[uid] = (time.time(), results, source)
    if not results:
        await msg.edit_text(t(uid, "recs_need_data"))
        return
    SEARCH[uid] = results
    lines = [t(uid, "recs_title_ai" if source == "ai" else "recs_title_google"), ""]
    kb = InlineKeyboardBuilder()
    for i, r in enumerate(results):
        lines.append(f"{i + 1}. <b>{escape(r['title'])}</b> — {escape(r['author'])}")
        if r.get("why"):
            lines.append(f"    <i>{escape(r['why'])}</i>")
        kb.button(text=f"➕ {r['title'][:35]}", callback_data=f"add:{i}")
    kb.adjust(1)
    await msg.edit_text("\n".join(lines), reply_markup=kb.as_markup())


# ---------- Итоги недели ----------
def week_bounds(offset: int = 0):
    """offset=0: эта неделя (пн..сегодня), 1: прошлая (пн..вс)."""
    today = now_local().date()
    mon = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
    return mon, (min(mon + timedelta(days=6), today) if offset == 0 else mon + timedelta(days=6))


def day_stats(uid: int, start: str, end: str) -> dict[str, tuple[int, int]]:
    return {
        r["day"]: (r["p"], r["mi"])
        for r in db.execute(
            "SELECT day, SUM(pages) p, SUM(minutes) mi FROM reading_log "
            "WHERE user_id=? AND day>=? AND day<=? GROUP BY day",
            (uid, start, end),
        )
    }


def week_recap(uid: int, offset: int = 0, allow_empty: bool = True) -> str | None:
    mon, end = week_bounds(offset)
    stats = day_stats(uid, mon.isoformat(), end.isoformat())
    total_p = sum(p for p, _ in stats.values())
    total_m = sum(mi for _, mi in stats.values())
    if not allow_empty and not stats:
        return None
    wd = t(uid, "weekdays").split()
    top = max([p for p, _ in stats.values()] + [1])
    sun = mon + timedelta(days=6)
    lines = [t(uid, "wk_head", a=mon.strftime("%d.%m"), b=sun.strftime("%d.%m")), ""]
    for i in range(7):
        p, mi = stats.get((mon + timedelta(days=i)).isoformat(), (0, 0))
        bar = "▓" * max(1, round(8 * p / top)) if p else ("▪" if mi else "·")
        lines.append(f"<code>{wd[i]}</code> {bar} {p}" if (p or mi) else f"<code>{wd[i]}</code> ·")
    lines.append("")
    lines.append(t(uid, "wk_total", p=total_p, tm=fmt_minutes(uid, total_m)))
    finished = db.execute(
        "SELECT COUNT(*) c FROM books WHERE user_id=? AND status='done' AND finished_at>=? AND finished_at<=?",
        (uid, mon.isoformat(), end.isoformat()),
    ).fetchone()["c"]
    lines.append(t(uid, "wk_books", n=finished))
    pmon, pend = week_bounds(offset + 1)
    prev = sum(p for p, _ in day_stats(uid, pmon.isoformat(), pend.isoformat()).values())
    if prev or total_p:
        lines.append(t(uid, "wk_diff", d=f"{total_p - prev:+d}"))
    cur, _ = streaks(uid)
    if cur:
        lines.append(t(uid, "streak_line", n=cur))
    return "\n".join(lines)


def week_kb(uid: int, offset: int):
    kb = InlineKeyboardBuilder()
    kb.button(
        text=("• " if offset == 0 else "") + t(uid, "wk_btn_this"), callback_data="week:0"
    )
    kb.button(
        text=("• " if offset == 1 else "") + t(uid, "wk_btn_last"), callback_data="week:1"
    )
    kb.adjust(2)
    return kb.as_markup()


@pr.message(Command("week"))
async def week_cmd(m: Message, command: CommandObject):
    uid = m.from_user.id
    arg = (command.args or "").strip().lower()
    if arg in ("on", "off"):
        db.execute("UPDATE users SET weekly_on=? WHERE user_id=?", (1 if arg == "on" else 0, uid))
        db.commit()
        await m.answer(t(uid, "wk_on" if arg == "on" else "wk_off"))
        return
    await m.answer(
        week_recap(uid, 0) + "\n\n" + t(uid, "wk_hint"), reply_markup=week_kb(uid, 0)
    )


@pr.callback_query(F.data.startswith("week:"))
async def cb_week(c: CallbackQuery):
    uid = c.from_user.id
    offset = 1 if c.data.endswith(":1") else 0
    await replace_text(c, week_recap(uid, offset) + "\n\n" + t(uid, "wk_hint"), week_kb(uid, offset))
    await c.answer()


# ---------- Импорт из CSV (Goodreads, Livelib и другие) ----------
IMPORT_COLS = {
    "title": ("title", "название", "название книги", "книга"),
    "author": ("author", "автор", "авторы"),
    "isbn": ("isbn13", "isbn", "исбн"),
    "rating": ("my rating", "rating", "моя оценка", "оценка"),
    "pages": ("number of pages", "pages", "количество страниц", "кол-во страниц", "страниц"),
    "year": ("year published", "original publication year", "год издания", "год", "year"),
    "date_read": ("date read", "дата прочтения", "прочитана", "дата"),
    "shelf": ("exclusive shelf", "shelf", "статус", "полка"),
    "shelves": ("bookshelves", "теги", "метки"),
}
SYSTEM_SHELVES = {"read", "to-read", "currently-reading", "did-not-finish", "dnf"}


def detect_columns(fieldnames: list[str]) -> dict[str, str | None]:
    low = {(f or "").strip().lower(): f for f in fieldnames}
    return {key: next((low[a] for a in aliases if a in low), None) for key, aliases in IMPORT_COLS.items()}


def parse_import_date(s: str | None) -> str | None:
    s = (s or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def map_status(shelf: str, has_date: bool) -> str:
    s = (shelf or "").strip().lower()
    if any(x in s for x in ("currently", "читаю", "читаем", "в процессе")):
        return "reading"
    if any(x in s for x in ("to-read", "want", "хочу", "планир", "отлож")):
        return "want"
    if any(x in s for x in ("did-not", "dnf", "dropped", "брос", "брош")):
        return "dropped"
    if any(x in s for x in ("read", "прочит", "готово")):
        return "done"
    return "done" if has_date else "want"


def to_int(s: str | None, lo: int, hi: int) -> int | None:
    m = re.search(r"\d+", (s or "").replace(" ", ""))
    return int(m.group()) if m and lo <= int(m.group()) <= hi else None


def import_rows(uid: int, rows: list[dict], cols: dict) -> tuple[int, int, int]:
    """Добавляет книги из строк CSV. Возвращает (добавлено, дублей, не разобрано)."""
    existing = {
        (norm_title(r["title"]), norm_title(r["author"]))
        for r in db.execute("SELECT title, author FROM books WHERE user_id=?", (uid,))
    }
    isbns = {
        r["isbn"] for r in db.execute("SELECT isbn FROM books WHERE user_id=? AND isbn IS NOT NULL", (uid,))
    }
    tag_ids: dict[str, int] = {}
    added = dups = bad = 0

    def val(row, key):
        col = cols.get(key)
        return (row.get(col) or "").strip() if col else ""

    for row in rows:
        title = val(row, "title")
        if not title:
            bad += 1
            continue
        author = val(row, "author") or "—"
        isbn = normalize_isbn(re.sub(r"\D", "", val(row, "isbn")) or "x")
        key = (norm_title(title), norm_title(author))
        if key in existing or (isbn and isbn in isbns):
            dups += 1
            continue
        finished = parse_import_date(val(row, "date_read"))
        status = map_status(val(row, "shelf"), bool(finished))
        pages = to_int(val(row, "pages"), 1, 10000)
        rating = to_int(val(row, "rating"), 1, 5)
        cur = db.execute(
            "INSERT INTO books (user_id, title, author, year, status, rating, pages, page, finished_at, isbn) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                uid, title[:200], author[:120], to_int(val(row, "year"), 1000, 2100), status, rating,
                pages, (pages or 0) if status == "done" else 0,
                finished if status == "done" else None, isbn,
            ),
        )
        existing.add(key)
        if isbn:
            isbns.add(isbn)
        added += 1
        for raw in val(row, "shelves").split(",")[:8]:
            name = norm_tag(raw)
            if not name or name in SYSTEM_SHELVES:
                continue
            if name not in tag_ids:
                r = db.execute("SELECT id FROM tags WHERE user_id=? AND name=?", (uid, name)).fetchone()
                tag_ids[name] = r["id"] if r else db.execute(
                    "INSERT INTO tags (user_id, name) VALUES (?,?)", (uid, name)
                ).lastrowid
            db.execute(
                "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?,?)", (cur.lastrowid, tag_ids[name])
            )
    db.commit()
    return added, dups, bad


def parse_csv_bytes(data: bytes):
    for enc in ("utf-8-sig", "cp1251"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("latin-1")
    first = text.split("\n", 1)[0]
    delim = max((",", ";", "\t"), key=first.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    for i, row in enumerate(reader):
        if i >= 3000:
            break
        rows.append({(k or "").strip().lower(): v for k, v in row.items()})
    cols = detect_columns(list(rows[0].keys())) if rows else {}
    # ключи строк уже в нижнем регистре, поэтому и колонки приводим к нижнему
    cols = {k: (v.strip().lower() if v else None) for k, v in cols.items()}
    return rows, cols


@pr.message(Command("import"))
async def import_help(m: Message):
    await m.answer(t(m.from_user.id, "import_help"))


async def import_csv(m: Message) -> None:
    uid = m.from_user.id
    doc = m.document
    if (doc.file_size or 0) > 5 * 1024 * 1024:
        await m.answer(t(uid, "import_big"))
        return
    msg = await m.answer(t(uid, "import_working"))
    try:
        buf = await m.bot.download(doc.file_id)
        rows, cols = parse_csv_bytes(buf.read())
    except Exception:
        logging.exception("csv read failed")
        await msg.edit_text(t(uid, "import_bad_format"))
        return
    if not rows or not cols.get("title"):
        await msg.edit_text(t(uid, "import_bad_format"))
        return
    added, dups, bad = import_rows(uid, rows, cols)
    await msg.edit_text(t(uid, "import_done", added=added, dups=dups, bad=bad))


# ======================================================================
#                              ГРУППЫ
# ======================================================================
def ensure_group(chat, lang: str | None = None) -> None:
    if db.execute("SELECT 1 FROM chat_groups WHERE chat_id=?", (chat.id,)).fetchone():
        db.execute("UPDATE chat_groups SET title=? WHERE chat_id=?", (chat.title, chat.id))
    else:
        db.execute(
            "INSERT INTO chat_groups (chat_id, title, lang) VALUES (?,?,?)",
            (chat.id, chat.title, lang or "ru"),
        )
    db.commit()


def group_lang(chat_id: int) -> str:
    r = db.execute("SELECT lang FROM chat_groups WHERE chat_id=?", (chat_id,)).fetchone()
    return r["lang"] if r and r["lang"] else "ru"


def join_group(chat_id: int, uid: int) -> bool:
    cur = db.execute(
        "INSERT OR IGNORE INTO group_members (chat_id, user_id) VALUES (?,?)", (chat_id, uid)
    )
    db.commit()
    return bool(cur.rowcount)


def drop_group(chat_id: int) -> None:
    db.execute("DELETE FROM chat_groups WHERE chat_id=?", (chat_id,))
    db.execute("DELETE FROM group_members WHERE chat_id=?", (chat_id,))
    db.commit()


def member_ids(chat_id: int) -> list[int]:
    return [
        r["user_id"]
        for r in db.execute("SELECT user_id FROM group_members WHERE chat_id=?", (chat_id,))
    ]


def period_range(period: str) -> tuple[str, str]:
    today = today_str()
    if period == "week":
        return week_start(), today
    if period == "month":
        return month_start(), today
    return today, today


def board_range(chat_id: int, start: str, end: str) -> list[dict]:
    rows = [
        {
            "uid": uid,
            "name": user_name(uid),
            "pages": pages_between(uid, start, end),
            "streak": streaks(uid)[0],
        }
        for uid in member_ids(chat_id)
    ]
    rows.sort(key=lambda r: (-r["pages"], r["name"].lower()))
    return rows


def board(chat_id: int, period: str) -> list[dict]:
    start, end = period_range(period)
    return board_range(chat_id, start, end)


def board_lines(active: list[dict], lang: str) -> list[str]:
    medals = ["🥇", "🥈", "🥉"]
    out = []
    for i, r in enumerate(active[:15]):
        mark = medals[i] if i < 3 else f"{i + 1}."
        line = f"{mark} {escape(r['name'])} — {tl(lang, 'g_pages', n=r['pages'])}"
        if r["streak"] > 1:
            line += f" 🔥{r['streak']}"
        out.append(line)
    return out


def board_text(chat_id: int, period: str, lang: str) -> str:
    rows = board(chat_id, period)
    if not rows:
        return tl(lang, "g_no_members", bot=BOT_USERNAME)
    out = [tl(lang, f"g_head_{period}", d=now_local().strftime("%d.%m"))]
    active = [r for r in rows if r["pages"] > 0]
    idle = [r for r in rows if r["pages"] == 0]
    if not active:
        out.append(tl(lang, "g_nobody"))
    out.extend(board_lines(active, lang))
    if idle:
        out.append("")
        out.append(tl(lang, "g_idle", names=", ".join(escape(r["name"]) for r in idle[:10])))
    return "\n".join(out)


def leader_line(chat_id: int, period: str, lang: str) -> str:
    rows = [r for r in board(chat_id, period) if r["pages"] > 0]
    if not rows:
        return ""
    return tl(lang, f"g_leader_{period}", name=escape(rows[0]["name"]), n=rows[0]["pages"])


def digest_text(chat_id: int, lang: str) -> str:
    parts = [board_text(chat_id, "day", lang)]
    leaders = [x for x in (leader_line(chat_id, p, lang) for p in ("week", "month")) if x]
    if leaders:
        parts.append("\n".join(leaders))
    ch = challenge_text(chat_id, lang, short=True)
    if ch:
        parts.append(ch)
    return "\n\n".join(parts)


def top_kb(lang: str, current: str):
    kb = InlineKeyboardBuilder()
    for p in ("day", "week", "month"):
        kb.button(text=("• " if p == current else "") + tl(lang, f"per_{p}"), callback_data=f"top:{p}")
    kb.adjust(3)
    return kb.as_markup()


async def is_admin(bot: Bot, chat_id: int, uid: int) -> bool:
    try:
        cm = await bot.get_chat_member(chat_id, uid)
        return cm.status in ("administrator", "creator")
    except Exception:
        return False


@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added(ev: ChatMemberUpdated):
    if ev.chat.type not in ("group", "supergroup"):
        return
    ensure_group(ev.chat, guess_lang(ev.from_user.language_code))
    await ev.answer(tl(group_lang(ev.chat.id), "g_hello", bot=BOT_USERNAME))


@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER >> IS_NOT_MEMBER))
async def bot_removed(ev: ChatMemberUpdated):
    if ev.chat.type in ("group", "supergroup"):
        drop_group(ev.chat.id)


@gr.message(Command("start", "help"))
async def g_help(m: Message):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    await m.answer(tl(group_lang(m.chat.id), "g_help", bot=BOT_USERNAME))


@gr.message(Command("join"))
async def g_join(m: Message):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    lang = group_lang(m.chat.id)
    name = escape(user_name(m.from_user.id))
    key = "g_joined" if join_group(m.chat.id, m.from_user.id) else "g_already"
    await m.answer(tl(lang, key, name=name, bot=BOT_USERNAME))


@gr.message(Command("leave"))
async def g_leave(m: Message):
    lang = group_lang(m.chat.id)
    db.execute(
        "DELETE FROM group_members WHERE chat_id=? AND user_id=?", (m.chat.id, m.from_user.id)
    )
    db.commit()
    await m.answer(tl(lang, "g_left", name=escape(user_name(m.from_user.id))))


@gr.message(Command("top"))
async def g_top(m: Message):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    lang = group_lang(m.chat.id)
    await m.answer(board_text(m.chat.id, "day", lang), reply_markup=top_kb(lang, "day"))


@gr.callback_query(F.data.startswith("top:"))
async def g_top_cb(c: CallbackQuery):
    period = c.data.split(":")[1]
    if period not in ("day", "week", "month"):
        return await c.answer()
    lang = group_lang(c.message.chat.id)
    try:
        await c.message.edit_text(
            board_text(c.message.chat.id, period, lang), reply_markup=top_kb(lang, period)
        )
    except TelegramBadRequest:
        pass  # текст не изменился
    await c.answer()


@gr.message(Command("read"))
async def g_read(m: Message, command: CommandObject):
    await read_impl(m, command, group=True)


@gr.message(Command("digest"))
async def g_digest(m: Message, command: CommandObject):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    lang = group_lang(m.chat.id)
    arg = (command.args or "").strip().lower()
    if not arg:
        r = db.execute("SELECT digest_time FROM chat_groups WHERE chat_id=?", (m.chat.id,)).fetchone()
        cur = r["digest_time"] if r else None
        await m.answer(tl(lang, "g_digest_cur", t=cur) if cur else tl(lang, "g_digest_off"))
        return
    if not await is_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer(tl(lang, "g_admin_only"))
        return
    if arg in ("off", "-", "0"):
        db.execute("UPDATE chat_groups SET digest_time=NULL WHERE chat_id=?", (m.chat.id,))
        db.commit()
        await m.answer(tl(lang, "g_digest_off_set"))
        return
    tm = parse_hhmm(arg)
    if not tm:
        await m.answer(tl(lang, "g_digest_usage"))
        return
    last = today_str() if time_passed_today(tm) else None  # прошло — начнём завтра
    db.execute(
        "UPDATE chat_groups SET digest_time=?, last_digest=? WHERE chat_id=?", (tm, last, m.chat.id)
    )
    db.commit()
    await m.answer(tl(lang, "g_digest_set", t=tm))


@gr.message(Command("lang"))
async def g_lang(m: Message):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    await m.answer(tl(group_lang(m.chat.id), "lang_prompt"), reply_markup=_glang_kb())


def _glang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="glang:ru")
    kb.button(text="🇬🇧 English", callback_data="glang:en")
    kb.adjust(2)
    return kb.as_markup()


@gr.callback_query(F.data.startswith("glang:"))
async def g_lang_cb(c: CallbackQuery):
    new = c.data.split(":")[1]
    lang = group_lang(c.message.chat.id)
    if new not in ("ru", "en"):
        return await c.answer()
    if not await is_admin(c.bot, c.message.chat.id, c.from_user.id):
        await c.answer(tl(lang, "g_admin_only"), show_alert=True)
        return
    db.execute("UPDATE chat_groups SET lang=? WHERE chat_id=?", (new, c.message.chat.id))
    db.commit()
    await c.message.edit_text(tl(new, "lang_set"))
    await c.answer()


# ---------- Челлендж группы и недельные итоги ----------
def month_days_left() -> int:
    today = now_local().date()
    return calendar.monthrange(today.year, today.month)[1] - today.day + 1


def challenge_info(chat_id: int):
    r = db.execute(
        "SELECT challenge_pages, challenge_done FROM chat_groups WHERE chat_id=?", (chat_id,)
    ).fetchone()
    if not r or not r["challenge_pages"]:
        return None
    rows = board_range(chat_id, month_start(), today_str())
    return r["challenge_pages"], sum(x["pages"] for x in rows), rows, r["challenge_done"]


def challenge_text(chat_id: int, lang: str, short: bool = False) -> str:
    info = challenge_info(chat_id)
    if not info:
        return ""
    target, done, rows, _ = info
    lines = [
        tl(lang, "ch_head"),
        tl(lang, "ch_progress", done=done, target=target, bar=bar10(done, target), pct=min(100, round(done * 100 / target))),
    ]
    if done >= target:
        lines.append(tl(lang, "ch_done"))
    else:
        days = month_days_left()
        lines.append(tl(lang, "ch_left", days=days, per=math.ceil((target - done) / days)))
    top = [r for r in rows if r["pages"] > 0][:5]
    if top and not short:
        lines.append(tl(lang, "ch_top", l=", ".join(f"{escape(r['name'])} {r['pages']}" for r in top)))
    return "\n".join(lines)


async def check_challenges(bot: Bot, uid: int) -> None:
    """После записи страниц: если у группы участника цель месяца выполнена, объявляем (один раз)."""
    ym = today_str()[:7]
    groups = db.execute(
        "SELECT g.* FROM chat_groups g JOIN group_members gm ON gm.chat_id=g.chat_id "
        "WHERE gm.user_id=? AND g.challenge_pages IS NOT NULL",
        (uid,),
    ).fetchall()
    for g in groups:
        if g["challenge_done"] == ym:
            continue
        info = challenge_info(g["chat_id"])
        if not info or info[1] < info[0]:
            continue
        db.execute("UPDATE chat_groups SET challenge_done=? WHERE chat_id=?", (ym, g["chat_id"]))
        db.commit()
        lang = g["lang"] or "ru"
        try:
            await bot.send_message(
                g["chat_id"],
                tl(lang, "ch_complete", target=info[0]) + "\n\n" + challenge_text(g["chat_id"], lang),
            )
        except TelegramForbiddenError:
            drop_group(g["chat_id"])
        except Exception:
            logging.exception("challenge announce failed for %s", g["chat_id"])


@gr.message(Command("challenge"))
async def g_challenge(m: Message, command: CommandObject):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    lang = group_lang(m.chat.id)
    arg = (command.args or "").strip().lower()
    if not arg:
        await m.answer(challenge_text(m.chat.id, lang) or tl(lang, "ch_none"))
        return
    if not await is_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer(tl(lang, "g_admin_only"))
        return
    if arg in ("off", "-", "0"):
        db.execute("UPDATE chat_groups SET challenge_pages=NULL WHERE chat_id=?", (m.chat.id,))
        db.commit()
        await m.answer(tl(lang, "ch_off"))
    elif arg.isdigit() and 50 <= int(arg) <= 1_000_000:
        db.execute(
            "UPDATE chat_groups SET challenge_pages=?, challenge_done=NULL WHERE chat_id=?",
            (int(arg), m.chat.id),
        )
        db.commit()
        await m.answer(tl(lang, "ch_set", n=int(arg)) + "\n\n" + challenge_text(m.chat.id, lang))
    else:
        await m.answer(tl(lang, "ch_usage"))


@gr.message(Command("weekly"))
async def g_weekly(m: Message, command: CommandObject):
    ensure_group(m.chat, guess_lang(m.from_user.language_code))
    lang = group_lang(m.chat.id)
    arg = (command.args or "").strip().lower()
    if arg not in ("on", "off"):
        r = db.execute("SELECT weekly_on FROM chat_groups WHERE chat_id=?", (m.chat.id,)).fetchone()
        await m.answer(tl(lang, "g_weekly_cur_on" if r and r["weekly_on"] else "g_weekly_cur_off"))
        return
    if not await is_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer(tl(lang, "g_admin_only"))
        return
    db.execute("UPDATE chat_groups SET weekly_on=? WHERE chat_id=?", (1 if arg == "on" else 0, m.chat.id))
    db.commit()
    await m.answer(tl(lang, "g_weekly_on" if arg == "on" else "g_weekly_off"))


def group_week_text(chat_id: int, lang: str) -> str:
    mon, sun = week_bounds(1)
    rows = board_range(chat_id, mon.isoformat(), sun.isoformat())
    active = [r for r in rows if r["pages"] > 0]
    out = [tl(lang, "gw_head", a=mon.strftime("%d.%m"), b=sun.strftime("%d.%m"))]
    if not active:
        out.append(tl(lang, "gw_empty"))
    else:
        out.extend(board_lines(active, lang))
        out.append("")
        out.append(tl(lang, "gw_total", p=sum(r["pages"] for r in active), n=len(active)))
        ids = [r["uid"] for r in rows]
        marks = ",".join("?" * len(ids))
        finished = db.execute(
            f"SELECT COUNT(*) c FROM books WHERE user_id IN ({marks}) AND status='done' "
            "AND finished_at>=? AND finished_at<=?",
            (*ids, mon.isoformat(), sun.isoformat()),
        ).fetchone()["c"]
        if finished:
            out.append(tl(lang, "gw_books", n=finished))
        best = max(rows, key=lambda r: r["streak"])
        if best["streak"] > 1:
            out.append(tl(lang, "gw_streak", name=escape(best["name"]), n=best["streak"]))
    ch = challenge_text(chat_id, lang, short=True)
    if ch:
        out.extend(["", ch])
    return "\n".join(out)


# ======================================================================
#   АДМИН: /id, /users, /backup, ежедневная копия базы, уведомления об ошибках
# ======================================================================
def is_owner(uid: int) -> bool:
    return bool(ADMIN_ID) and uid == ADMIN_ID


def get_meta(key: str) -> str | None:
    r = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def set_meta(key: str, value: str) -> None:
    db.execute(
        "INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    db.commit()


@pr.message(Command("id"))
async def id_cmd(m: Message):
    await m.answer(t(m.from_user.id, "your_id", id=m.from_user.id))


def admin_stats() -> str:
    today = now_local().date()
    iso = lambda n: (today - timedelta(days=n)).isoformat()

    def one(sql: str, *args) -> int:
        return db.execute(sql, args).fetchone()[0] or 0

    total = one("SELECT COUNT(*) FROM users")
    lines = [
        "📊 <b>Статистика бота</b>",
        "",
        f"👥 Пользователей: {total} (🇷🇺 {one('SELECT COUNT(*) FROM users WHERE lang=?', 'ru')} · 🇬🇧 {one('SELECT COUNT(*) FROM users WHERE lang=?', 'en')})",
        f"🆕 Новых: сегодня {one('SELECT COUNT(*) FROM users WHERE joined_at>=?', iso(0))}"
        f" · 7 дн. {one('SELECT COUNT(*) FROM users WHERE joined_at>=?', iso(6))}"
        f" · 30 дн. {one('SELECT COUNT(*) FROM users WHERE joined_at>=?', iso(29))}",
        f"🟢 Активных: сегодня {one('SELECT COUNT(*) FROM users WHERE last_seen>=?', iso(0))}"
        f" · 7 дн. {one('SELECT COUNT(*) FROM users WHERE last_seen>=?', iso(6))}"
        f" · 30 дн. {one('SELECT COUNT(*) FROM users WHERE last_seen>=?', iso(29))}",
        "",
        f"📚 Добавили книги: {one('SELECT COUNT(DISTINCT user_id) FROM books')} польз. · всего книг {one('SELECT COUNT(*) FROM books')}",
        f"📄 Записали страницы за 7 дн.: {one('SELECT COUNT(DISTINCT user_id) FROM reading_log WHERE day>=?', iso(6))} польз. "
        f"({one('SELECT SUM(pages) FROM reading_log WHERE day>=?', iso(6))} стр.)",
        f"👥 Групп: {one('SELECT COUNT(*) FROM chat_groups')} · участников рейтинга {one('SELECT COUNT(*) FROM group_members')}",
    ]
    src = db.execute(
        "SELECT COALESCE(source, 'прямой заход') s, COUNT(*) c FROM users "
        "WHERE joined_at IS NOT NULL GROUP BY s ORDER BY c DESC LIMIT 15"
    ).fetchall()
    if src:
        lines += ["", "🔗 <b>Откуда пришли</b> (после включения учёта):"]
        lines += [f"   {escape(r['s'])} — {r['c']}" for r in src]
    old = one("SELECT COUNT(*) FROM users WHERE joined_at IS NULL")
    if old:
        lines.append(f"   до учёта — {old}")
    return "\n".join(lines)


@pr.message(Command("users"))
async def users_cmd(m: Message):
    if is_owner(m.from_user.id):
        await m.answer(admin_stats())


def make_backup() -> tuple[str, bytes]:
    """Консистентная копия базы (sqlite backup API) + хранение 14 дней в папке backups."""
    os.makedirs("backups", exist_ok=True)
    name = f"tomik-{today_str()}.db"
    path = os.path.join("backups", name)
    dst = sqlite3.connect(path)
    try:
        db.backup(dst)
    finally:
        dst.close()
    cutoff = time.time() - 14 * 86400
    for f in os.listdir("backups"):
        fp = os.path.join("backups", f)
        if f.startswith("tomik-") and os.path.getmtime(fp) < cutoff:
            os.remove(fp)
    with open(path, "rb") as fh:
        return name, fh.read()


async def send_backup(bot: Bot) -> None:
    try:
        name, data = make_backup()
        if len(data) > 49 * 1024 * 1024:
            await bot.send_message(ADMIN_ID, "⚠️ База больше 49 МБ, Telegram не примет такой файл.")
            return
        await bot.send_document(
            ADMIN_ID,
            BufferedInputFile(data, filename=name),
            caption=f"💾 Резервная копия базы ({max(1, len(data) // 1024)} КБ)",
        )
    except Exception:
        logging.exception("backup failed")


@pr.message(Command("backup"))
async def backup_cmd(m: Message):
    if is_owner(m.from_user.id):
        await send_backup(m.bot)


async def set_admin_commands(bot: Bot) -> None:
    cmds = [BotCommand(command=c, description=tl("ru", f"cmd_{c}")) for c in (
        "shelf", "timer", "recs", "stats", "week", "goal", "remind", "add", "import", "read", "export", "lang", "cancel"
    )]
    cmds += [
        BotCommand(command="users", description="Статистика бота"),
        BotCommand(command="backup", description="Копия базы сейчас"),
        BotCommand(command="id", description="Мой Telegram ID"),
    ]
    await bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=ADMIN_ID))


_last_error_ts = 0.0


@dp.errors()
async def on_error(event: ErrorEvent):
    """Любая необработанная ошибка в обработчиках: в лог и (не чаще раза в минуту) тебе в личку."""
    global _last_error_ts
    logging.error("handler error: %r", event.exception, exc_info=event.exception)
    if ADMIN_ID and BOT_REF and time.time() - _last_error_ts > 60:
        _last_error_ts = time.time()
        try:
            msg = f"{type(event.exception).__name__}: {event.exception}"[:300]
            await BOT_REF.send_message(ADMIN_ID, f"⚠️ <b>Ошибка в боте</b>\n<code>{escape(msg)}</code>")
        except Exception:
            pass
    return True


# ======================================================================
#                   ФОНОВЫЕ ЗАДАЧИ: напоминания и итоги дня
# ======================================================================
async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            now = now_local()
            now_min = now.hour * 60 + now.minute
            today = now.date().isoformat()

            for u in db.execute("SELECT * FROM users WHERE remind_time IS NOT NULL").fetchall():
                h, mi = map(int, u["remind_time"].split(":"))
                if 0 <= now_min - (h * 60 + mi) < 10 and u["last_reminded"] != today:
                    db.execute("UPDATE users SET last_reminded=? WHERE user_id=?", (today, u["user_id"]))
                    db.commit()
                    try:
                        await send_reminder(bot, u["user_id"])
                    except TelegramForbiddenError:
                        db.execute("UPDATE users SET remind_time=NULL WHERE user_id=?", (u["user_id"],))
                        db.commit()
                    except Exception:
                        logging.exception("reminder failed for %s", u["user_id"])

            for g in db.execute("SELECT * FROM chat_groups WHERE digest_time IS NOT NULL").fetchall():
                h, mi = map(int, g["digest_time"].split(":"))
                if 0 <= now_min - (h * 60 + mi) < 10 and g["last_digest"] != today:
                    db.execute("UPDATE chat_groups SET last_digest=? WHERE chat_id=?", (today, g["chat_id"]))
                    db.commit()
                    if not member_ids(g["chat_id"]):
                        continue
                    try:
                        await bot.send_message(g["chat_id"], digest_text(g["chat_id"], g["lang"] or "ru"))
                    except TelegramForbiddenError:
                        drop_group(g["chat_id"])
                    except Exception:
                        logging.exception("digest failed for %s", g["chat_id"])

            if ADMIN_ID and now_min >= 240 and get_meta("last_backup") != today:  # копия базы после 04:00
                set_meta("last_backup", today)
                await send_backup(bot)

            if now.weekday() == 0 and 600 <= now_min < 610:  # понедельник 10:00: итоги прошлой недели
                for u in db.execute(
                    "SELECT user_id FROM users WHERE weekly_on=1 AND (weekly_last IS NULL OR weekly_last != ?)",
                    (today,),
                ).fetchall():
                    db.execute("UPDATE users SET weekly_last=? WHERE user_id=?", (today, u["user_id"]))
                    db.commit()
                    try:
                        text = week_recap(u["user_id"], 1, allow_empty=False)
                        if text:
                            await bot.send_message(u["user_id"], text)
                    except TelegramForbiddenError:
                        db.execute("UPDATE users SET weekly_on=0 WHERE user_id=?", (u["user_id"],))
                        db.commit()
                    except Exception:
                        logging.exception("weekly failed for %s", u["user_id"])
                for g in db.execute(
                    "SELECT * FROM chat_groups WHERE weekly_on=1 AND (weekly_last IS NULL OR weekly_last != ?)",
                    (today,),
                ).fetchall():
                    db.execute("UPDATE chat_groups SET weekly_last=? WHERE chat_id=?", (today, g["chat_id"]))
                    db.commit()
                    if not member_ids(g["chat_id"]):
                        continue
                    try:
                        await bot.send_message(g["chat_id"], group_week_text(g["chat_id"], g["lang"] or "ru"))
                    except TelegramForbiddenError:
                        drop_group(g["chat_id"])
                    except Exception:
                        logging.exception("group weekly failed for %s", g["chat_id"])
        except Exception:
            logging.exception("background loop error")
        await asyncio.sleep(30)


async def set_commands(bot: Bot) -> None:
    private = [
        "shelf", "timer", "recs", "stats", "week", "goal", "remind",
        "add", "import", "read", "export", "lang", "cancel",
    ]
    groups = ["join", "leave", "top", "read", "challenge", "weekly", "digest", "lang"]
    for code in (None, "en"):
        lang = code or "ru"
        kw = {"language_code": code} if code else {}
        await bot.set_my_commands(
            [BotCommand(command=c, description=tl(lang, f"cmd_{c}")) for c in private],
            scope=BotCommandScopeAllPrivateChats(),
            **kw,
        )
        await bot.set_my_commands(
            [BotCommand(command=c, description=tl(lang, f"cmd_{c}")) for c in groups],
            scope=BotCommandScopeAllGroupChats(),
            **kw,
        )


dp.message.outer_middleware(UserMiddleware())
dp.callback_query.outer_middleware(UserMiddleware())
dp.include_router(pr)
dp.include_router(gr)


async def main():
    global BOT_USERNAME, BOT_REF
    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    BOT_REF = bot
    BOT_USERNAME = (await bot.get_me()).username or ""
    try:
        await set_commands(bot)
        if ADMIN_ID:
            await set_admin_commands(bot)
    except Exception:
        logging.exception("не удалось выставить меню команд")
    task = asyncio.create_task(reminder_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())