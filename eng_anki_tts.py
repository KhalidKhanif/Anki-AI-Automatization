#!/usr/bin/env python3
"""
Автоозвучка английской колоды YOMITAN_ENG в Anki (бесплатные голоса Microsoft Edge).

  Sentence -> SentenceAudioEng  (английское предложение)
  Word     -> WordAudioEng      (английское слово)

Русские переводы не озвучиваются.
Обычно отдельно запускать не нужно: eng_add_cards.py вызывает его сам.

Заполняются только ПУСТЫЕ аудиополя, уже озвученное не трогается.

Подготовка (один раз):
  python3 -m pip install -r requirements.txt     (Windows: py -m pip install -r requirements.txt)

Запуск (Anki открыт, окна редактирования и браузер карточек закрыты):
  python3 eng_anki_tts.py --limit 2    # проба на двух заметках
  python3 eng_anki_tts.py              # озвучить всё, что ещё не озвучено

Добавить карточки и сразу озвучить:
  python3 eng_add_cards.py && python3 eng_anki_tts.py
"""

import argparse
import asyncio
import base64
import hashlib
import html
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    import edge_tts
except ImportError:
    sys.exit("Не установлена библиотека edge-tts. Выполните: python3 -m pip install -r requirements.txt  (Windows: py -m pip install -r requirements.txt)")

ANKI_URL = "http://127.0.0.1:8765"
DECK = "YOMITAN_ENG"

EN_VOICE = "en-US-AndrewNeural"     # мужской американский; можно en-US-AriaNeural, en-GB-RyanNeural, en-GB-SoniaNeural

# (поле-источник, поле-назначение, голос)
JOBS = [
    ("Sentence", "SentenceAudioEng", EN_VOICE),
    ("Word", "WordAudioEng", EN_VOICE),
]


def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(ANKI_URL, payload)) as resp:
        data = json.load(resp)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["result"]


def clean_text(raw: str) -> str:
    """Убирает HTML, [sound:], пояснения в скобках."""
    text = re.sub(r"\[sound:[^\]]*\]", "", raw)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


async def synthesize(text: str, voice: str) -> bytes:
    last = None
    for _ in range(3):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out.mp3"
                await edge_tts.Communicate(text, voice).save(str(out))
                data = out.read_bytes()
                if data:
                    return data
        except Exception as exc:
            last = exc
            await asyncio.sleep(1)
    raise RuntimeError(f"синтез не удался: {last}")


async def process_note(note: dict) -> int:
    note_id = note["noteId"]
    fields = {name: f["value"] for name, f in note["fields"].items()}
    new_values = {}

    for src, dst, voice in JOBS:
        if src not in fields or dst not in fields:
            print(f"  - {note_id}: нет поля {src} или {dst} (поля заметки: {', '.join(fields)})")
            continue
        if fields[dst].strip():
            continue
        text = clean_text(fields[src])
        if not text:
            print(f"  - {note_id}: {src} пустое, озвучивать нечего")
            continue
        try:
            audio = await synthesize(text, voice)
        except Exception as exc:
            print(f"  ! {note_id} {src}: {exc}")
            continue
        digest = hashlib.md5(f"{voice}:{text}".encode("utf-8")).hexdigest()[:12]
        filename = f"tts_{digest}.mp3"
        anki("storeMediaFile", filename=filename, data=base64.b64encode(audio).decode("ascii"))
        new_values[dst] = f"[sound:{filename}]"

    if new_values:
        try:
            anki("updateNoteFields", note={"id": note_id, "fields": new_values})
        except Exception as exc:
            print(f"  ! {note_id}: не удалось записать ({exc}). Закройте браузер карточек и окна редактирования.")
            return 0
    return len(new_values)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="ограничить число заметок")
    parser.add_argument("--notes", default="", help="id заметок через запятую (передаёт add_cards)")
    parser.add_argument("--all", action="store_true", help="проверить всю колоду")
    args = parser.parse_args()

    try:
        anki("version")
    except Exception as exc:
        sys.exit(f"Нет связи с AnkiConnect ({ANKI_URL}). Запущен ли Anki?\n{exc}")

    if args.notes:
        ids = [int(x) for x in args.notes.split(",") if x.strip()]
    elif args.all:
        ids = anki("findNotes", query=f'deck:"{DECK}"')
    else:
        # только заметки, где хотя бы одно аудиополе пустое
        empty = " OR ".join(f'"{dst}:"' for _, dst, _ in JOBS)
        ids = anki("findNotes", query=f'deck:"{DECK}" ({empty})')
    if not ids:
        print("Озвучивать нечего — всё уже озвучено.")
        return
    if args.limit:
        ids = ids[: args.limit]
    notes = anki("notesInfo", notes=ids)
    print(f"Озвучиваю заметок: {len(notes)}")

    total = 0
    for i, note in enumerate(notes, 1):
        added = await process_note(note)
        total += added
        print(f"[{i}/{len(notes)}] {note['noteId']}: добавлено аудио: {added}")

    print(f"Готово. Всего добавлено аудиофайлов: {total}")


if __name__ == "__main__":
    asyncio.run(main())
