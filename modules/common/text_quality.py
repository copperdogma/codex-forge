import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from modules.common.utils import english_wordlist


_WORD_RE = re.compile(r"[A-Za-z]+")
_ORDINAL_RE = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)
_PAGES_N_RE = re.compile(r"^pages?\d+$", re.IGNORECASE)


def _ascii_alpha_lower(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    if not s:
        return None
    if not all("a" <= ch <= "z" for ch in s):
        return None
    return s


def _iter_words(text: str) -> Iterable[str]:
    for m in _WORD_RE.finditer(text or ""):
        w = _ascii_alpha_lower(m.group(0))
        if w:
            yield w


@lru_cache(maxsize=1)
def load_default_wordlist() -> Set[str]:
    """
    Best-effort English wordlist for spell/garble detection.

    Priority order:
    1) `CODEX_WORDLIST_PATH` env var (newline-delimited words).
    2) System dictionaries (common macOS/Linux locations).
    3) Repo-local lightweight fallback (`english_wordlist()`).
    """
    env_path = os.environ.get("CODEX_WORDLIST_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)
    candidates.extend([
        # Traditional word lists
        "/usr/share/dict/words",
        "/usr/dict/words",
        "/usr/share/dict/web2",
        # Hunspell/MySpell dictionaries (common on macOS/Linux)
        "/System/Library/Spelling/en_US.dic",
        "/System/Library/Spelling/en_GB.dic",
        "/Library/Spelling/en_US.dic",
        "/Library/Spelling/en_GB.dic",
        "/usr/share/hunspell/en_US.dic",
        "/usr/share/hunspell/en_GB.dic",
        "/usr/share/myspell/dicts/en_US.dic",
        "/usr/share/myspell/dicts/en_GB.dic",
    ])

    vocab: Set[str] = set()

    for p in candidates:
        try:
            path = Path(p)
            if not path.exists() or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                # Hunspell .dic entries are often "word/FLAGS". Take the word part.
                raw = (line or "").split("/", 1)[0]
                w = _ascii_alpha_lower(raw)
                if w:
                    vocab.add(w)
            if vocab:
                break
        except Exception:
            continue

    if not vocab:
        vocab = set(english_wordlist())
    else:
        vocab.update(english_wordlist())

    return vocab


def spell_garble_metrics(lines: List[str], *, vocab: Optional[Set[str]] = None, max_examples: int = 10) -> Dict[str, Any]:
    """
    Compute lightweight spell/garble metrics from OCR lines.
    Higher scores indicate worse quality.
    """
    text = "\n".join(lines or [])
    vocab = vocab or load_default_wordlist()

    alpha_words = list(_iter_words(text))
    total_words = len(alpha_words)

    def _in_vocab(word: str) -> bool:
        if word in vocab:
            return True
        # Generic plural normalization to reduce false OOV for common plurals when only singular is present.
        if word.endswith("ies") and len(word) > 4 and (word[:-3] + "y") in vocab:
            return True
        if word.endswith("es") and len(word) > 3 and word[:-2] in vocab:
            return True
        if word.endswith("s") and len(word) > 3 and word[:-1] in vocab:
            return True
        return False

    oov_words: List[str] = [w for w in alpha_words if not _in_vocab(w)]
    oov = len(oov_words)
    oov_ratio = (oov / total_words) if total_words else 0.0

    # "Suspicious" OOV words: consonant-heavy fragments often produced by OCR (e.g., "sxrll" for "skill").
    vowels = set("aeiouy")
    suspicious_oov: List[str] = []
    for w in oov_words:
        if len(w) < 4:
            continue
        if not any(ch in vowels for ch in w):
            suspicious_oov.append(w)
    suspicious_oov_count = len(suspicious_oov)

    def _examples_with_counts(items: List[str]) -> List[Tuple[str, int]]:
        counts: Dict[str, int] = {}
        for it in items:
            key = (it or "").strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:max_examples]

    tokens = (text or "").split()
    mixed_tokens: List[str] = []
    suspicious_mixed_tokens: List[str] = []
    digit_fixed_tokens: List[str] = []
    alpha_fixed_tokens: List[str] = []

    leet_digits = set("0134579")
    leet_map = {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "9": "g",
    }

    # Alpha-only confusions that frequently show up in OCR.
    # Keep this tight to avoid over-triggering: this story explicitly calls out K↔x and I↔r.
    alpha_confusions = {
        "x": "k",
        "k": "x",
        "r": "i",
        "i": "r",
    }

    def _confusable_to_vocab(word: str, *, max_subs: int = 2, max_states: int = 256) -> Optional[str]:
        """
        Return a vocab word reachable by applying up to max_subs single-character confusion substitutions.
        Intended for alpha-only tokens like 'sxrll' → 'skill' (x→k, r→i).
        """
        if not word or word in vocab:
            return None
        if len(word) < 4 or len(word) > 24:
            return None
        if not any(ch in alpha_confusions for ch in word):
            return None

        seen = {word}
        frontier: List[Tuple[str, int]] = [(word, 0)]
        while frontier and len(seen) <= max_states:
            cur, depth = frontier.pop(0)
            if depth >= max_subs:
                continue
            for i, ch in enumerate(cur):
                rep = alpha_confusions.get(ch)
                if not rep:
                    continue
                nxt = cur[:i] + rep + cur[i + 1 :]
                if nxt in seen:
                    continue
                if nxt in vocab:
                    return nxt
                seen.add(nxt)
                frontier.append((nxt, depth + 1))
                if len(seen) > max_states:
                    break
        return None

    for tok in tokens:
        raw = (tok or "").strip().strip(".,;:!?()[]{}<>\"'")
        if not raw:
            continue
        # Ignore common, generally-legit mixed tokens.
        # These appear in normal prose/front matter and are not OCR garble.
        if _ORDINAL_RE.match(raw) or _PAGES_N_RE.match(raw):
            continue
        has_alpha = any(ch.isalpha() for ch in raw)
        has_digit = any(ch.isdigit() for ch in raw)

        # Digit/letter confusions: if de-leeting yields a known word, treat this as a strong confusion signal,
        # including for short tokens like "y0u" or "t0".
        if has_alpha and has_digit and len(raw) >= 2:
            fixed = "".join(leet_map.get(ch, ch) for ch in raw.lower())
            fixed_alpha = _ascii_alpha_lower(fixed)
            if fixed_alpha and fixed_alpha != _ascii_alpha_lower(raw) and fixed_alpha in vocab:
                digit_fixed_tokens.append(f"{raw}->{fixed_alpha}")

            # Heuristic: flag as "suspicious" only when it contains common OCR/leet digits
            # and is long enough to be plausibly a corrupted word (avoid short codes like "1B4").
            if len(raw) >= 4 and any(ch in leet_digits for ch in raw):
                suspicious_mixed_tokens.append(raw)
            if len(raw) >= 3:
                mixed_tokens.append(raw)

        # Alpha-only confusions (x↔k, r↔i): attempt a tiny search for a close vocab word.
        if has_alpha and not has_digit:
            alpha = _ascii_alpha_lower(raw)
            if alpha and alpha not in vocab:
                cand = _confusable_to_vocab(alpha)
                if cand:
                    alpha_fixed_tokens.append(f"{raw}->{cand}")
    mixed_ratio = (len(mixed_tokens) / len(tokens)) if tokens else 0.0

    # Score: emphasize dictionary misses, but also penalize strong "fragment" signals even if ratio is low.
    # Higher score = worse.
    dictionary_score = min(1.0, max(oov_ratio, 0.5 if suspicious_oov_count > 0 else 0.0))
    # Confusion score: any "fixed-to-vocab" token is a strong signal even if ratio is small.
    confusion_bonus = 0.0
    if suspicious_mixed_tokens:
        confusion_bonus = max(confusion_bonus, 0.6)
    if digit_fixed_tokens:
        confusion_bonus = max(confusion_bonus, 0.5)
    if alpha_fixed_tokens:
        confusion_bonus = max(confusion_bonus, 0.5)
    confusion_score = min(1.0, max(mixed_ratio * 2.0, confusion_bonus))

    return {
        "dictionary_score": round(dictionary_score, 4),
        "dictionary_oov_ratio": round(oov_ratio, 4),
        "dictionary_total_words": total_words,
        "dictionary_oov_words": oov,
        "dictionary_oov_examples": _examples_with_counts(oov_words),
        "dictionary_suspicious_oov_words": suspicious_oov_count,
        "dictionary_suspicious_oov_examples": _examples_with_counts(suspicious_oov),
        "char_confusion_score": round(confusion_score, 4),
        "char_confusion_mixed_ratio": round(mixed_ratio, 4),
        "char_confusion_examples": _examples_with_counts(mixed_tokens),
        "char_confusion_suspicious_examples": _examples_with_counts(suspicious_mixed_tokens),
        "char_confusion_digit_fixed_words": len(digit_fixed_tokens),
        "char_confusion_digit_fixed_examples": _examples_with_counts(digit_fixed_tokens),
        "char_confusion_alpha_fixed_words": len(alpha_fixed_tokens),
        "char_confusion_alpha_fixed_examples": _examples_with_counts(alpha_fixed_tokens),
    }
