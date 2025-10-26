# CSV 경로를 지금 구조에 맞춰 자동 탐색해서, 실제 intakes/data/mfds_foods.csv를 확실히 읽도록 수정
# 기존 코드와의 호환성 유지: find_food, DEFAULT_ENTRY 그대로.
# 백/프런트에서 바로 쓰기 좋은 표준 키(kcal/protein_g/carb_g/fat_g)로 변환 + 총합 계산 헬퍼를 제공해서,ai/views.py에서 to_per100g(entry)와 compute_total_from_entry(entry, weight_g)만 호출하면 끝
"""
Utility helpers for looking up nutrition information from the MFDS CSV.

Keeps the original public API:
- find_food(label) -> Optional[FoodEntry]
- DEFAULT_ENTRY: FoodEntry

Improvements:
- Robust CSV path resolution (settings.MFDS_FOOD_CSV -> intakes/data/mfds_foods.csv -> ai/mfds_foods.csv)
- Stronger normalization (NFKC + strip non-alnum/KR)
- Helpers for per-100g and total macros:
    - to_per100g(entry) -> {kcal, protein_g, carb_g, fat_g}
    - compute_total_from_entry(entry, weight_g) -> same keys, scaled by weight_g
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

# --- CSV path resolution ------------------------------------------------------

def _resolve_csv_path() -> Path:
    """
    1) settings.MFDS_FOOD_CSV
    2) <BASE_DIR>/intakes/data/mfds_foods.csv
    3) <this_dir>/mfds_foods.csv
    """
    try:
        from django.conf import settings
        p = getattr(settings, "MFDS_FOOD_CSV", None)
        if p:
            pth = Path(p)
            if pth.exists():
                return pth
            # If MFDS_FOOD_CSV was relative, try BASE_DIR join
            base = getattr(settings, "BASE_DIR", None)
            if base:
                p2 = Path(base) / p
                if p2.exists():
                    return p2
        # default to BASE_DIR/intakes/data
        if base := getattr(settings, "BASE_DIR", None):
            cand = Path(base) / "intakes" / "data" / "mfds_foods.csv"
            if cand.exists():
                return cand
    except Exception:
        # settings may not be ready in some contexts
        pass

    # fallback to local (ai/mfds_foods.csv)
    return Path(__file__).resolve().parent / "mfds_foods.csv"


CSV_PATH = _resolve_csv_path()

# --- Normalization / parsing --------------------------------------------------

_NORMALIZE_RE = re.compile(r"[^0-9a-zA-Z가-힣]")

def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return _NORMALIZE_RE.sub("", text).lower().strip()

def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None

@dataclass(frozen=True)
class FoodEntry:
    label_ko: str
    serving_size: Optional[str]
    # NOTE: These are per-100g semantics in MFDS CSV
    # keys follow existing code: 'calories','protein','carb','fat'
    macros: Dict[str, Optional[float]]
    source: str = "csv"

def _iter_synonyms(row: Dict[str, str]) -> Iterable[str]:
    names = set()
    for key in ("식품명", "대표식품명", "식품중분류명", "식품소분류명"):
        value = (row.get(key) or "").strip()
        if not value:
            continue
        names.add(value)
        # split on whitespace/underscore to add granular tokens (helps fuzzy)
        names.update(part.strip() for part in value.replace("_", " ").split() if part.strip())
    return names

# --- Index building -----------------------------------------------------------

@lru_cache(maxsize=1)
def _build_index() -> Tuple[Dict[str, FoodEntry], Iterable[str]]:
    index: Dict[str, FoodEntry] = {}
    aliases = []

    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                label = (row.get("식품명") or "").strip()
                if not label:
                    continue
                macros = {
                    # MFDS are per 100g
                    "calories": _to_float(row.get("에너지(kcal)")),
                    "protein":  _to_float(row.get("단백질(g)")),
                    "carb":     _to_float(row.get("탄수화물(g)")),
                    "fat":      _to_float(row.get("지방(g)")),
                }
                entry = FoodEntry(
                    label_ko=label,
                    serving_size=(row.get("영양성분함량기준량") or "").strip() or None,
                    macros=macros,
                    source="csv",
                )
                for synonym in _iter_synonyms(row):
                    key = _normalize(synonym)
                    if not key:
                        continue
                    if key not in index:
                        index[key] = entry
                        aliases.append(key)

    return index, aliases

# --- English fallback ---------------------------------------------------------

_ENGLISH_FALLBACK = {
    "bibimbap":    FoodEntry("비빔밥", None, {"calories": 550, "protein": 22, "carb": 72, "fat": 18}, source="fallback"),
    "bulgogi":     FoodEntry("불고기", None, {"calories": 480, "protein": 32, "carb": 28, "fat": 24}, source="fallback"),
    "kimbap":      FoodEntry("김밥",   None, {"calories": 390, "protein": 13, "carb": 52, "fat": 12}, source="fallback"),
    "ramen":       FoodEntry("라면",   None, {"calories": 470, "protein": 15, "carb": 64, "fat": 16}, source="fallback"),
    "kimchijjigae":FoodEntry("김치찌개",None, {"calories": 320, "protein": 20, "carb": 16, "fat": 18}, source="fallback"),
    "tteokbokki":  FoodEntry("떡볶이", None, {"calories": 520, "protein": 11, "carb": 86, "fat": 12}, source="fallback"),
    "friedchicken":FoodEntry("치킨",   None, {"calories": 640, "protein": 34, "carb": 32, "fat": 40}, source="fallback"),
    "pizza":       FoodEntry("피자",   None, {"calories": 620, "protein": 26, "carb": 64, "fat": 26}, source="fallback"),
    "salad":       FoodEntry("샐러드", None, {"calories": 220, "protein": 8,  "carb": 18, "fat": 12}, source="fallback"),
    "sushi":       FoodEntry("스시",   None, {"calories": 320, "protein": 24, "carb": 42, "fat": 6},  source="fallback"),
    "sandwich":    FoodEntry("샌드위치",None,{"calories": 430, "protein": 20, "carb": 48, "fat": 16}, source="fallback"),
    "pasta":       FoodEntry("파스타", None, {"calories": 520, "protein": 20, "carb": 74, "fat": 14}, source="fallback"),
    "yogurt":      FoodEntry("요거트", None, {"calories": 180, "protein": 12, "carb": 18, "fat": 6},  source="fallback"),
    "toast":       FoodEntry("토스트", None, {"calories": 310, "protein": 10, "carb": 38, "fat": 12}, source="fallback"),
    "steak":       FoodEntry("스테이크",None, {"calories": 680, "protein": 55, "carb": 0,  "fat": 50}, source="fallback"),
    "hamburger":   FoodEntry("햄버거", None, {"calories": 540, "protein": 28, "carb": 45, "fat": 28}, source="fallback"),
    "curry":       FoodEntry("카레",   None, {"calories": 490, "protein": 18, "carb": 60, "fat": 20}, source="fallback"),
    "apple":       FoodEntry("사과",   None, {"calories": 95,  "protein": 0.5,"carb": 25, "fat": 0.3},source="fallback"),
    "banana":      FoodEntry("바나나", None, {"calories": 105, "protein": 1.3,"carb": 27, "fat": 0.4},source="fallback"),
    "coffee":      FoodEntry("커피",   None, {"calories": 5,   "protein": 0.1,"carb": 0,  "fat": 0},  source="fallback"),
}

DEFAULT_ENTRY = FoodEntry(
    label_ko="일반 식사",
    serving_size=None,
    macros={"calories": 450, "protein": 20, "carb": 55, "fat": 16},
    source="default",
)

# --- Public lookup ------------------------------------------------------------

def find_food(label: Optional[str]) -> Optional[FoodEntry]:
    key = _normalize(label)
    if not key:
        return None

    index, aliases = _build_index()
    entry = index.get(key)
    if entry:
        return entry

    # Fuzzy lookup for KR tokens
    candidates = get_close_matches(key, aliases, n=1, cutoff=0.90)
    if candidates:
        match = candidates[0]
        candidate_entry = index.get(match)
        if candidate_entry:
            return candidate_entry

    # English fallback
    fallback = _ENGLISH_FALLBACK.get(key)
    if fallback:
        return fallback

    return None

# --- Helpers for per-100g / total macros -------------------------------------

def to_per100g(entry: FoodEntry) -> Dict[str, float]:
    """
    Convert FoodEntry.macros to standard keys used by API/front:
    kcal, protein_g, carb_g, fat_g (all per 100g)

    If carb or fat is missing but calories and protein exist,
    estimate using remaining calories:
    - Protein: 4 kcal/g
    - Carb: 4 kcal/g
    - Fat: 9 kcal/g
    - Typical ratio: carb 40%, fat 60% of remaining calories
    """
    m = entry.macros or {}
    kcal = float(m.get("calories") or 0.0)
    protein_g = float(m.get("protein") or 0.0)
    carb_g = float(m.get("carb") or 0.0)
    fat_g = float(m.get("fat") or 0.0)

    # If missing carb or fat but have calories and protein, estimate
    if kcal > 0 and protein_g > 0 and (carb_g == 0 or fat_g == 0):
        protein_kcal = protein_g * 4  # 단백질 칼로리
        remaining_kcal = max(0, kcal - protein_kcal)

        if carb_g == 0 and fat_g == 0:
            # 둘 다 없으면 40:60 비율로 배분
            carb_kcal = remaining_kcal * 0.40
            fat_kcal = remaining_kcal * 0.60
            carb_g = round(carb_kcal / 4, 1)
            fat_g = round(fat_kcal / 9, 1)
        elif carb_g == 0:
            # 지방만 있으면 나머지를 탄수화물로
            fat_kcal = fat_g * 9
            carb_kcal = max(0, remaining_kcal - fat_kcal)
            carb_g = round(carb_kcal / 4, 1)
        elif fat_g == 0:
            # 탄수화물만 있으면 나머지를 지방으로
            carb_kcal = carb_g * 4
            fat_kcal = max(0, remaining_kcal - carb_kcal)
            fat_g = round(fat_kcal / 9, 1)

    return {
        "kcal": kcal,
        "protein_g": protein_g,
        "carb_g": carb_g,
        "fat_g": fat_g,
    }

def compute_total_from_entry(entry: FoodEntry, weight_g: Optional[float]) -> Dict[str, float]:
    """
    Scale per-100g macros by weight_g (defaults to 100g if None/invalid).
    """
    w = 100.0
    try:
        if weight_g is not None:
            w = max(float(weight_g), 1.0)
    except Exception:
        w = 100.0
    per100 = to_per100g(entry)
    factor = w / 100.0
    return {
        "kcal": round(per100["kcal"] * factor, 1),
        "protein_g": round(per100["protein_g"] * factor, 1),
        "carb_g": round(per100["carb_g"] * factor, 1),
        "fat_g": round(per100["fat_g"] * factor, 1),
    }

__all__ = [
    "FoodEntry",
    "find_food",
    "DEFAULT_ENTRY",
    "to_per100g",
    "compute_total_from_entry",
]
