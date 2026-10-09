import re

label_before_bullet_regex = re.compile(
    r"(?<=[\w.)])\s{2,}([A-Z][\w ]{2,30}):\s+-\s(?=[A-Z'\w\"\u2018])"
)
label_same_line_regex = re.compile(
    r"(?<=[\w.)]) ([A-Z][\w ]{2,30}): -\s"
)
num_range_1_regex = re.compile(r"(\d[\d.]*)\s-\s(\d[\d.]*)")
num_range_2_regex = re.compile(r"(\d[\d.]*)\s\u2013\s(\d[\d.]*)")
inline_bullet_1_regex = re.compile(r"(?<=[\w.)])\s+-\s")
inline_bullet_2_regex = re.compile(r"(?<=:\s)-\s")
inline_bullet_3_regex = re.compile(r"(?<=[\w.)])(\s)\u2013\s")
split_topic_regex = re.compile(r"^[A-Z][\w']")
split_punct_regex = re.compile(r"[.)]\s*-\s")
is_label_regex = re.compile(r"^\*\*[A-Z][\w ]{2,30}:\*\*\s*$")
bold_plain_label_regex = re.compile(r"^([A-Z][\w ]{2,30}):\s*$")
consecutive_newlines_regex = re.compile(r"\n{3,}")

def format_bullets(text: str) -> str:
    if not text:
        return text

    lines = text.split("\n")
    out = []
    for line in lines:
        line = label_before_bullet_regex.sub(r"\n**\1:**\n- ", line)
        line = label_same_line_regex.sub(r" \n**\1:**\n- ", line)

        def rng(m):
            return "\x00RNG%s,%s\x00" % (m.group(1), m.group(2))

        line = num_range_1_regex.sub(rng, line)
        line = num_range_2_regex.sub(rng, line)
        line = inline_bullet_1_regex.sub("\n- ", line)
        line = inline_bullet_2_regex.sub("\n- ", line)
        line = inline_bullet_3_regex.sub("\n- ", line)
        line = re.sub(r"\x00RNG([\d.]+),([\d.]+)\x00", r"\1 - \2", line)

        def split_chained(l):
            out_lines = []
            first = True
            pos = 0
            for m in re.finditer(r"\s-\s", l):
                if first:
                    first = False
                    continue
                start = m.start()
                after = l[start + 3:].strip()
                if split_topic_regex.match(after) or split_punct_regex.search(l[:start][-2:] + "-"):
                    out_lines.append(l[pos:start])
                    pos = start + 3
            out_lines.append(l[pos:])
            return [o for o in out_lines if o.strip()]

        if line.startswith("- ") and line.count(" - ") > 1:
            chunks = split_chained(line)
            if len(chunks) > 1:
                line = "\n".join(c if i == 0 else "- " + c.strip()
                                 for i, c in enumerate(chunks))
        out.append(line)

    joined = "\n".join(out)

    if joined:
        def bold_plain_label(line):
            m = bold_plain_label_regex.match(line)
            return ("**%s:**" % m.group(1)) if m else line

        joined = "\n".join(bold_plain_label(l) if not is_label_regex.match(l) else l
                           for l in joined.split("\n"))

        def is_bullet(line):
            return line.startswith("- ")

        compact = []
        prev = None
        for line in joined.split("\n"):
            line = line.rstrip()
            if prev is not None:
                if is_label_regex.match(line):
                    if is_bullet(prev) or prev == "":
                        compact.append(line)
                    else:
                        compact.append("")
                        compact.append(line)
                elif is_bullet(line):
                    if prev == "":
                        compact[-1] = line
                    else:
                        compact.append(line)
                else:
                    if is_bullet(prev):
                        compact.append("")
                    elif prev == "":
                        if line:
                            compact.append(line)
                    else:
                        compact.append(line)
            else:
                compact.append(line)
            prev = line
        joined = "\n".join(compact)
        joined = consecutive_newlines_regex.sub("\n\n", joined)
    return joined.strip()
