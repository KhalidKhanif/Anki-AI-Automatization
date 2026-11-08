#!/usr/bin/env python3
"""
Добавляет карточки из файла arb_cards.jsonl в колоду YOMITAN_ARB через AnkiConnect
и сразу озвучивает их через arb_anki_tts.py.
Не требует никаких платных сервисов, всё работает на вашем компьютере.

Требования:
  1. Anki запущен, установлено дополнение AnkiConnect (код 2055492159).
  2. Python 3.8+ (сторонние библиотеки не нужны).

Формат arb_cards.jsonl: одна карточка = одна строка JSON, например:
  {"word": "تسريح", "translation": "увольнение", "sentence": "...<b>...</b>...",
   "sentence_translation": "...", "transcription": "تَسْرِيحٌ", "image_url": ""}

Поле image_url необязательное: если указано, картинка скачивается
(с заголовком браузера, поэтому Unsplash и др. не блокируют) и кладётся в поле Picture.

Запуск:
  python arb_add_cards.py              # читает arb_cards.jsonl рядом со скриптом
  python arb_add_cards.py мои.jsonl    # или другой файл
"""

import base64
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ANKI_URL = "http://127.0.0.1:8765"
DECK = "YOMITAN_ARB"
MODEL = "YOMITAN_ASBPLAYER"


def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(ANKI_URL, payload)) as resp:
        data = json.load(resp)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["result"]


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def make_picture(card: dict) -> str:
    url = card.get("image_url", "").strip()
    if not url:
        return ""
    filename = "img_" + hashlib.md5(card["word"].encode("utf-8")).hexdigest()[:10] + ".jpg"
    data = download(url)
    anki("storeMediaFile", filename=filename, data=base64.b64encode(data).decode("ascii"))
    return f'<img src="{filename}">'


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("arb_cards.jsonl"))
    try:
        anki("version")
    except Exception as exc:
        sys.exit(f"Нет связи с AnkiConnect ({ANKI_URL}). Запущен ли Anki?\n{exc}")

    added = failed = 0
    new_ids = []
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    keep = []  # строки, которые не удалось добавить (останутся в файле)
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            card = json.loads(line)
        except Exception as exc:
            print(f"[{n}] ошибка в строке файла ({exc}), оставляю её в файле")
            keep.append(line)
            failed += 1
            continue
        try:
            picture = make_picture(card)
        except Exception as exc:
            print(f"[{n}] {card['word']}: картинка не скачалась ({exc}), добавляю без неё")
            picture = ""
        note = {
            "deckName": DECK,
            "modelName": MODEL,
            "fields": {
                "Word": card["word"],
                "WordTranslation": card["translation"],
                "WordAudioRus": "",
                "Sentence": card["sentence"],
                "SentenceTranslation": card["sentence_translation"],
                "SentenceAudioEng": "",
                "Transcription": card["transcription"],
                "Picture": picture,
                "WordAudioEng": "",
                "SentenceAudioRus": "",
            },
            "options": {"allowDuplicate": False},
            "tags": [],
        }
        try:
            new_ids.append(anki("addNote", note=note))
            added += 1
            print(f"[{n}] {card['word']}: добавлено")
        except Exception as exc:
            if "duplicate" in str(exc).lower() and picture:
                try:
                    ids = anki("findNotes", query=f'deck:"{DECK}" "Word:{card["word"]}"')
                    info = anki("notesInfo", notes=ids)
                    if info and not info[0]["fields"]["Picture"]["value"].strip():
                        anki("updateNoteFields", note={"id": info[0]["noteId"], "fields": {"Picture": picture}})
                        new_ids.append(info[0]["noteId"])
                        added += 1
                        print(f"[{n}] {card['word']}: уже была, добавлена картинка")
                        continue
                except Exception as exc2:
                    print(f"[{n}] {card['word']}: не удалось обновить картинку ({exc2})")
            failed += 1
            if "duplicate" in str(exc).lower():
                print(f"[{n}] {card['word']}: уже есть в колоде, пропущено")
            else:
                keep.append(line)
                print(f"[{n}] {card['word']}: ошибка ({exc}), оставлено в файле")

    print(f"Готово. Добавлено: {added}, пропущено: {failed}")

    # обработанные строки -> архив, в файле остаются только неудавшиеся
    done = [l for l in lines if l.strip() and l not in keep]
    if done:
        archive = Path(__file__).with_name("arb_cards_added.jsonl")
        with archive.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(done) + "\n")
    path.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    print(f"Файл {path.name} очищен" + (f", в нём осталось строк с ошибками: {len(keep)}" if keep else "") + ".")

    if not new_ids:
        return
    print("\nОзвучка новых слов...")
    subprocess.run([sys.executable, str(Path(__file__).with_name("arb_anki_tts.py")),
                    "--notes", ",".join(map(str, new_ids))])


if __name__ == "__main__":
    main()
