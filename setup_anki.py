#!/usr/bin/env python3
"""
Первичная настройка Anki: создаёт тип записи YOMITAN_ASBPLAYER и колоды
YOMITAN_ENG и YOMITAN_ARB, если их ещё нет. Запускается ОДИН раз.
Уже существующие колоды и типы записей не изменяются.

Требования: Anki открыт, установлено дополнение AnkiConnect (код 2055492159).

Запуск:
  macOS:   python3 setup_anki.py
  Windows: py setup_anki.py
"""
import json
import sys
import urllib.request

ANKI_URL = "http://127.0.0.1:8765"
MODEL = "YOMITAN_ASBPLAYER"
DECKS = ["YOMITAN_ENG", "YOMITAN_ARB"]
FIELDS = [
    "Word", "WordTranslation", "WordAudioRus", "Sentence", "SentenceTranslation",
    "SentenceAudioEng", "Transcription", "Picture", "WordAudioEng", "SentenceAudioRus",
]

FRONT = """<div class="word" dir="auto">{{Word}}</div>
{{#Picture}}<div class="pic">{{Picture}}</div>{{/Picture}}
{{WordAudioEng}}"""

BACK = """{{FrontSide}}
<hr id="answer">
<div class="transcription" dir="auto">{{Transcription}}</div>
<div class="translation">{{WordTranslation}}</div>
<div class="sentence" dir="auto">{{Sentence}} {{SentenceAudioEng}}</div>
<div class="sentence-tr">{{SentenceTranslation}}</div>"""

CSS = """.card { font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 20px;
  text-align: center; color: #1e293b; background: #f8fafc; padding: 12px; }
.nightMode.card, .night_mode .card { color: #f1f5f9; background: #0f172a; }
.word { font-size: 2.2em; font-weight: 700; margin: 10px 0; }
.pic img { max-width: 100%; max-height: 40vh; border-radius: 12px; }
.transcription { font-size: 1.3em; color: #64748b; margin: 8px 0; }
.translation { font-size: 1.4em; font-weight: 600; color: #3b82f6; margin: 8px 0; }
.sentence { font-size: 1.15em; margin: 16px 0 6px; line-height: 1.7; }
.sentence-tr { color: #64748b; }"""


def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(ANKI_URL, payload)) as resp:
        data = json.load(resp)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["result"]


def main():
    try:
        anki("version")
    except Exception as exc:
        sys.exit(f"Нет связи с AnkiConnect ({ANKI_URL}). Запущен ли Anki и установлен ли AnkiConnect?\n{exc}")

    if MODEL in anki("modelNames"):
        missing = [f for f in FIELDS if f not in anki("modelFieldNames", modelName=MODEL)]
        if missing:
            sys.exit(f"Тип записи «{MODEL}» уже есть, но в нём не хватает полей: {', '.join(missing)}.\n"
                     "Добавьте их в Anki: Инструменты → Управление типами записей → Поля.")
        print(f"Тип записи «{MODEL}» уже есть — не трогаю.")
    else:
        anki("createModel", modelName=MODEL, inOrderFields=FIELDS, css=CSS, isCloze=False,
             cardTemplates=[{"Name": "Card 1", "Front": FRONT, "Back": BACK}])
        print(f"Создан тип записи «{MODEL}».")

    existing = set(anki("deckNames"))
    for deck in DECKS:
        if deck in existing:
            print(f"Колода «{deck}» уже есть — не трогаю.")
        else:
            anki("createDeck", deck=deck)
            print(f"Создана колода «{deck}».")

    print("\nГотово! Теперь можно добавлять карточки (см. README).")


if __name__ == "__main__":
    main()
