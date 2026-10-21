#!/usr/bin/env python3
"""One-off, auditable translation completion from public EN interface strings.

Uses an Apache-2.0 Helsinki-NLP model on a disposable Actions runner, never
during HA runtime. Existing human translations always take precedence.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/announcement_hub"
FRONTEND = COMPONENT / "frontend"
TRANSLATIONS = COMPONENT / "translations"
MUL = {
    "fr": "fra", "es": "spa", "it": "ita",
    "pt": "por", "pt-BR": "por", "nl": "nld", "pl": "pol",
    "ru": "rus", "tr": "tur", "uk": "ukr", "ar": "ara",
    "zh-Hans": "cmn_Hans", "zh-Hant": "cmn_Hant", "ja": "jpn",
    "sv": "swe", "cs": "ces", "ko": None,
}
# Technical tokens, placeholders, addresses, identifiers and values must
# remain byte-identical; never permit a model to translate them.
PROTECTED = re.compile(
    r"(\{[A-Za-z_][A-Za-z_0-9]*\}"
    r"|https?://[^\s)]+|[a-z][a-z0-9_]*\.[a-z0-9_.]+"
    r"|\b[a-z]+_[a-z0-9_]+\b|\b\d+(?:[.,/]\d+)*\b)"
)
DIGITS = re.compile(r"\d+(?:[.,/]\d+)*")
INTERP = re.compile(r"\{[A-Za-z_][A-Za-z_0-9]*\}")
IDENTITY = {
    "TTS", "AI", "AI Task", "Home Assistant", "Announcement Hub",
    "Companion App", "Snapcast", "Snapserver", "MPD", "Debug", "Info",
    "0%", "25%", "50%", "75%", "100%",
}

class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.keys = OrderedDict()
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        for name, value in attrs:
            if name in ("placeholder", "aria-label", "title") and value:
                self.keys[value] = None

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, value):
        stripped = value.strip()
        if stripped and not self._skip and re.search(r"[a-zA-Z]", stripped):
            self.keys[stripped] = None

def flatten(source, prefix=""):
    result = {}
    if isinstance(source, str):
        result[prefix] = source
    elif isinstance(source, dict):
        for key, value in source.items():
            result.update(flatten(value, f"{prefix}.{key}" if prefix else key))
    return result

def replace_values(source, english, translated):
    if isinstance(source, dict):
        return {
            key: replace_values(value, english[key], translated)
            for key, value in source.items()
        }
    if source != english or source in IDENTITY or not source.strip():
        return source
    return translated.get(source, source)

def candidate_texts(en, target, english_card, locale_card):
    native = flatten(en)
    existing = flatten(target)
    needs = {
        string for key, string in native.items()
        if existing.get(key) == string and string not in IDENTITY
    }
    needs |= {
        key for key in english_card
        if key not in locale_card and key not in IDENTITY
        and re.search(r"[a-zA-Z]", key)
    }
    return sorted(needs, key=lambda s: (len(s), s))

def translate_batch(model, tokenizer, target, items):
    import torch
    if not items:
        return []
    prepared = [(">>" + target + "<< " if target else "") + text for text in items]
    encoded = tokenizer(prepared, padding=True, truncation=True,
                        max_length=256, return_tensors="pt")
    with torch.inference_mode():
        out = model.generate(**encoded, max_new_tokens=256, num_beams=2,
                             renormalize_logits=True)
    return [s.strip() for s in tokenizer.batch_decode(
        out, skip_special_tokens=True)]

def safe_candidate(original, candidate):
    if not candidate or len(candidate) > max(35, 4 * len(original)):
        return False
    if sorted(INTERP.findall(original)) != sorted(INTERP.findall(candidate)):
        return False
    if sorted(DIGITS.findall(original)) != sorted(DIGITS.findall(candidate)):
        return False
    if any(word in original and word not in candidate
           for word in ("Home Assistant", "Snapcast", "TTS", "MPD")):
        return False
    return True

def translate_one(model, tokenizer, code, source, cache):
    if source in cache:
        return cache[source]
    pieces = PROTECTED.split(source)
    indices = [i for i, part in enumerate(pieces)
               if i % 2 == 0 and part.strip()]
    translated = translate_batch(model, tokenizer, code, [pieces[i] for i in indices])
    for i, target in zip(indices, translated):
        pieces[i] = target
    rendered = "".join(pieces)
    # Fallback means no invented UI semantics, but does not claim completion.
    cache[source] = rendered if safe_candidate(source, rendered) else source
    return cache[source]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=list(MUL))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    en = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    localepath = FRONTEND / "announcement-hub-locales.json"
    card = json.loads(localepath.read_text(encoding="utf-8"))
    collector = TextCollector()
    collector.feed((FRONTEND / "announcement-hub-card.html").read_text(encoding="utf-8"))
    js = (FRONTEND / "announcement-hub-card.js").read_text(encoding="utf-8")
    # JS dynamic notification strings plus static/card-editor English labels.
    for literal in re.findall(r'_t\("((?:[^"\\]|\\.)*)"', js):
        collector.keys[literal] = None
    for old in card.values():
        for key in old:
            collector.keys[key] = None
    english_card = sorted(collector.keys)

    import torch
    from transformers import MarianMTModel, MarianTokenizer
    torch.set_num_threads(3)
    model_name = "Helsinki-NLP/opus-mt-en-mul"
    model = MarianMTModel.from_pretrained(model_name).eval()
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    ko_model = ko_tokenizer = None

    for lang in args.languages:
        if lang in ("en", "el", "de"):
            print(f"{lang}: existing human translation preserved")
            continue
        if lang not in MUL:
            raise ValueError(f"Unknown locale: {lang}")
        path = TRANSLATIONS / (lang + ".json")
        existing = json.loads(path.read_text(encoding="utf-8"))
        current_card = dict(card.get(lang, {}))
        code = MUL[lang]
        if code is None:
            # Separate Korean-capable Apache-2.0 Marian model.
            if ko_model is None:
                ko_name = "Helsinki-NLP/opus-mt-tc-big-en-ko"
                ko_model = MarianMTModel.from_pretrained(ko_name).eval()
                ko_tokenizer = MarianTokenizer.from_pretrained(ko_name)
            active_model, active_tokenizer = ko_model, ko_tokenizer
        else:
            active_model, active_tokenizer = model, tokenizer

        candidates = candidate_texts(en, existing, english_card, current_card)
        if args.limit:
            candidates = candidates[:args.limit]
        cache = {}
        for i, source in enumerate(candidates, 1):
            translate_one(active_model, active_tokenizer, code, source, cache)
            if i % 25 == 0:
                print(f"{lang}: {i}/{len(candidates)}", flush=True)
        new_locale = dict(current_card)
        for key in english_card:
            if key not in new_locale and key in cache:
                new_locale[key] = cache[key]
        new_translations = replace_values(existing, en, cache)
        count = sum(a != b for a, b in zip(
            flatten(new_translations).values(), flatten(en).values()))
        incomplete = [key for key, value in flatten(en).items()
                      if flatten(new_translations).get(key) == value
                      and value not in IDENTITY]
        print(f"{lang}: translated {len(cache)} unique source strings; "
              f"{count}/{len(flatten(en))} native entries localized; "
              f"English fallbacks: {len(incomplete)}", flush=True)
        if not args.dry_run:
            path.write_text(json.dumps(new_translations, ensure_ascii=False,
                            indent=2) + "\n", encoding="utf-8")
            card[lang] = new_locale
    if not args.dry_run:
        localepath.write_text(json.dumps(card, ensure_ascii=False, indent=2)
                              + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
