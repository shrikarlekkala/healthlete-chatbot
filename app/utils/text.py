import re
from typing import Optional, Tuple

decision_line_regex = re.compile(
    r"^\s*ANSWER\s*:\s*(PROFILE|INSUFFICIENT|OFF[_\s-]?TOPIC)\s*\n?",
    re.IGNORECASE,
)
legacy_route_token_regex = re.compile(r"\[\s*ROUTE\s*:[^\]]*\]", re.IGNORECASE)
link_regex = re.compile(
    r"\[([^\]]*)\]\(\s*https?://[^\)]*\s*\)|https?://\S+", re.IGNORECASE)
utm_regex = re.compile(r"\?utm_[a-z_]+", re.IGNORECASE)
domain_mention_regex = re.compile(r"\(\s*[A-Za-z0-9.-]+\.[a-z]{2,6}\s*\)")
bold_regex = re.compile(r"\*{2,3}([^*]+)\*{2,3}")
header_regex = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
standalone_hashes_regex = re.compile(r"(?<!\w)#+(?![\w.#])")
backtick_regex = re.compile(r"`+([^`]*)`+")
emoji_regex = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F0FF"
    "\U00002600-\U000027BF\U0000FE00-\U0000FE0F\u2B50\u2764\u00A9\u00AE]",
    re.UNICODE)
decision_anywhere_regex = re.compile(r"ANSWER\s*:\s*(PROFILE|INSUFFICIENT|OFF[_\s-]?TOPIC)",
                                   re.IGNORECASE)

def clean_body_text(text: str) -> str:
    text = legacy_route_token_regex.sub("", text)
    text = decision_anywhere_regex.sub("", text)
    return re.sub(r"\s+", " ", text).strip()

def sanitize_answer(text: str) -> str:
    def link_replace(match):
        title = match.group(1)
        return title if title else ""
    text = link_regex.sub(link_replace, text)
    text = utm_regex.sub("", text)
    text = domain_mention_regex.sub("", text)
    text = bold_regex.sub(r"\1", text)
    text = header_regex.sub("", text)
    text = standalone_hashes_regex.sub("", text)
    text = backtick_regex.sub(r"\1", text)
    text = emoji_regex.sub("", text)
    text = text.replace("*", "")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

def parse_decision(answer: str) -> Tuple[Optional[str], str]:
    text = answer or ""
    if legacy_route_token_regex.search(text):
        first, _, rest = text.partition("\n")
        first = legacy_route_token_regex.sub("", first)
        text = (first + "\n" + rest).strip()

    match = decision_line_regex.match(text)
    if not match:
        first, _, rest = text.partition("\n")
        line_match = decision_line_regex.match(first)
        if line_match:
            route = re.sub(r"[\s-]", "_", line_match.group(1).upper())
            body = clean_body_text(first[line_match.end():] + "\n" + rest)
            return route, body
        anywhere = decision_anywhere_regex.search(text)
        if anywhere:
            route = re.sub(r"[\s-]", "_", anywhere.group(1).upper())
            body = clean_body_text(text)
            return route, body
        return None, clean_body_text(text)

    route = re.sub(r"[\s-]", "_", match.group(1).upper())
    body = clean_body_text(text[match.end():])
    return route, body
