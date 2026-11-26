import re

MALAYALAM_RE = re.compile(r"[\u0D00-\u0D7F]")
MANGGLISH_HINTS = {
    "entha", "engane", "evide", "aanu", "undo", "venam", "cheyyam",
    "cheyyanam", "parayu", "parayamo", "ariyamo", "njan", "ningal",
    "ente", "ningalkku", "ivide", "avide", "illa", "aayirikkum",
}


def detect_language(text: str, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if MALAYALAM_RE.search(text):
        return "ml"
    words = {word.strip(".,?!:;()[]{}").lower() for word in text.split()}
    if words & MANGGLISH_HINTS:
        return "manglish"
    return "en"
