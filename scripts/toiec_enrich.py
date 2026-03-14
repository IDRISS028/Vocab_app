"""
toeic_enrich.py
---------------
Enrichit la liste de mots TOEIC via un LLM (API compatible OpenAI / LM Studio).
Pour chaque mot, le LLM retourne :
  - type grammatical (noun, verb, adjective, adverb, phrase…)
  - traduction française
  - 3 phrases exemples en anglais + leur traduction française

Résultat : toeic_enriched.csv
Colonnes : id, word, type, translation_fr,
           example_1_en, example_1_fr, example_2_en, example_2_fr, example_3_en, example_3_fr,
           scramble_easy_sentence, scramble_easy_words,
           scramble_medium_sentence, scramble_medium_words,
           scramble_hard_sentence, scramble_hard_words

Usage :
    python toeic_enrich.py \
        --input  toeic_words.csv \
        --output toeic_enriched.csv \
        --base-url http://localhost:1234/v1 \
        --model  <nom-du-modele> \
        --workers 4
"""

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

# ── Prompt système ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a professional English-French linguist specialized in TOEIC vocabulary.
For each English word or phrase given, respond ONLY with a valid JSON object (no markdown, no extra text) with exactly these keys:
{
  "type": "<noun | verb | adjective | adverb | phrase | conjunction | preposition | pronoun | interjection>",
  "translation_fr": "<French translation, concise>",
  "examples": [
    {"en": "<example sentence 1 in English>", "fr": "<French translation of sentence 1>"},
    {"en": "<example sentence 2 in English>", "fr": "<French translation of sentence 2>"},
    {"en": "<example sentence 3 in English>", "fr": "<French translation of sentence 3>"}
  ],
  "scramble": {
    "easy":   {"sentence": "<simple English sentence, 5-10 words>",   "words": "<word1 / word2 / ...>"},
    "medium": {"sentence": "<moderate English sentence, 11-15 words>", "words": "<word1 / word2 / ...>"},
    "hard":   {"sentence": "<complex English sentence, 16-20 words>",  "words": "<word1 / word2 / ...>"}
  }
}
Rules:
- All sentences (examples AND scramble) must be in ENGLISH.
- Examples must be realistic TOEIC-style sentences (business, travel, daily life context).
- Scramble sentences MUST BE COMPLETELY DIFFERENT from the 3 examples. Do NOT reuse any example sentence.
- Scramble words field: take ALL words from the sentence (including punctuation attached to words), shuffle them randomly, and join with ' / '.
- Return ONLY the JSON, nothing else.
"""

# ── Appel LLM ─────────────────────────────────────────────────────────────────
def call_llm(client: OpenAI, model: str, word: str, retries: int = 3) -> dict:
    """Appelle le LLM et retourne un dict enrichi pour le mot donné."""
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Word: {word}"},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            raw = response.choices[0].message.content.strip()

            # Nettoyer les éventuels blocs markdown ```json … ```
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            data = json.loads(raw)

            # Validation minimale
            assert "type" in data
            assert "translation_fr" in data
            assert len(data.get("examples", [])) == 3
            assert "scramble" in data and all(k in data["scramble"] for k in ("easy", "medium", "hard"))

            return data

        except (json.JSONDecodeError, AssertionError, KeyError) as e:
            print(f"  ⚠️  Réponse invalide pour '{word}' (tentative {attempt+1}/{retries}): {e}")
            time.sleep(1)
        except Exception as e:
            print(f"  ❌ Erreur API pour '{word}' (tentative {attempt+1}/{retries}): {e}")
            time.sleep(2)

    # Valeur de repli si toutes les tentatives échouent
    return {
        "type": "unknown",
        "translation_fr": "",
        "examples": [
            {"en": "", "fr": ""},
            {"en": "", "fr": ""},
            {"en": "", "fr": ""},
        ],
        "scramble": {
            "easy":   {"sentence": "", "words": ""},
            "medium": {"sentence": "", "words": ""},
            "hard":   {"sentence": "", "words": ""},
        },
    }


# ── Traitement d'une ligne ────────────────────────────────────────────────────
def process_row(client: OpenAI, model: str, row: dict) -> dict:
    word = row["word"]
    print(f"  🔍 Traitement : {word}")
    data = call_llm(client, model, word)
    ex  = data["examples"]
    sc  = data["scramble"]
    return {
        "id":                     row["id"],
        "word":                   word,
        "type":                   data["type"],
        "translation_fr":         data["translation_fr"],
        "example_1_en":           ex[0]["en"],
        "example_1_fr":           ex[0]["fr"],
        "example_2_en":           ex[1]["en"],
        "example_2_fr":           ex[1]["fr"],
        "example_3_en":           ex[2]["en"],
        "example_3_fr":           ex[2]["fr"],
        "scramble_easy_sentence":   sc["easy"]["sentence"],
        "scramble_easy_words":      sc["easy"]["words"],
        "scramble_medium_sentence": sc["medium"]["sentence"],
        "scramble_medium_words":    sc["medium"]["words"],
        "scramble_hard_sentence":   sc["hard"]["sentence"],
        "scramble_hard_words":      sc["hard"]["words"],
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Enrichit la liste TOEIC via LLM.")
    parser.add_argument("--input",    default="../data/words.csv",    help="CSV source (word, section, type)")
    parser.add_argument("--output",   default="../data/toeic_enriched.csv", help="CSV de sortie enrichi")
    parser.add_argument("--base-url", default="http://localhost:1234/v1", help="URL de l'API LM Studio")
    parser.add_argument("--model",    default="openai/gpt-oss-20b",        help="Nom du modèle LM Studio")
    parser.add_argument("--api-key",  default="0",          help="Clé API (lm-studio par défaut)")
    parser.add_argument("--workers",  type=int, default=4,          help="Nombre de threads parallèles")
    parser.add_argument("--limit",    type=int, default=None,       help="Limiter à N mots (test)")
    parser.add_argument("--resume",   action="store_true",          help="Reprendre depuis le dernier mot traité")
    args = parser.parse_args()

    # ── Client OpenAI compatible LM Studio
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    # ── Lecture du CSV source
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Normaliser la colonne "mot" → "word" si nécessaire
    for row in rows:
        if "mot" in row and "word" not in row:
            row["word"] = row.pop("mot")

    # Ajouter un id si absent
    for i, row in enumerate(rows, start=1):
        if "id" not in row or not row["id"]:
            row["id"] = str(i)

    if args.limit:
        rows = rows[:args.limit]

    # ── Reprise : charger les mots déjà traités
    already_done = set()
    output_path = Path(args.output)
    if args.resume and output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            done_reader = csv.DictReader(f)
            for r in done_reader:
                already_done.add(r["word"])
        print(f"♻️  Reprise : {len(already_done)} mots déjà traités (dernière ligne source : {len(already_done)}).")

    rows_todo = [r for r in rows if r["word"] not in already_done]
    print(f"📋 {len(rows_todo)} mots à traiter (sur {len(rows)} total)\n")

    # ── CSV de sortie
    fieldnames = [
        "id", "word", "type", "translation_fr",
        "example_1_en", "example_1_fr",
        "example_2_en", "example_2_fr",
        "example_3_en", "example_3_fr",
        "scramble_easy_sentence",   "scramble_easy_words",
        "scramble_medium_sentence", "scramble_medium_words",
        "scramble_hard_sentence",   "scramble_hard_words",
    ]

    write_header = not (args.resume and output_path.exists())
    out_file = open(output_path, "a" if args.resume else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    if write_header:
        writer.writeheader()

    # ── Traitement parallèle
    completed = 0
    failed    = 0
    last_word = None
    last_line = len(already_done)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_row, client, args.model, row): row
            for row in rows_todo
        }

        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                writer.writerow(result)
                out_file.flush()   # écriture immédiate → reprise possible
                completed += 1
                last_line += 1
                last_word = result['word']
                print(f"  ✅ [{completed}/{len(rows_todo)}] {result['word']} (ligne {last_line})")
            except Exception as e:
                failed += 1
                print(f"  ❌ Échec pour '{row['word']}' : {e}")

    out_file.close()

    print(f"\n{'─'*50}")
    print(f"✅ Terminé : {completed} mots enrichis, {failed} échecs")
    print(f"📁 Fichier : {output_path.resolve()}")
    print(f"📌 Dernière ligne traitée : {last_line} ({last_word})")
    print(f"💡 Pour continuer : python toiec_enrich.py --resume")


if __name__ == "__main__":
    main()