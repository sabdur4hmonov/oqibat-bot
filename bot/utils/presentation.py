"""Bounded HTML for Telegram: count UTF-16 and never cut a tag or entity."""

from html import escape
from html.parser import HTMLParser
from textwrap import wrap


def units(value):
    return len(value.encode("utf-16-le")) // 2


class CompactHTML(HTMLParser):
    def __init__(self, limit, width):
        super().__init__(convert_charrefs=True)
        self.limit, self.width, self.used = limit - 1, width, 0
        self.parts, self.tags = [], []
        self.cut = False

    def handle_starttag(self, tag, attrs):
        if not self.cut and tag in {"b", "i", "u", "s", "code", "pre", "a", "tg-spoiler"}:
            attributes = ""
            if tag == "a":
                href = dict(attrs).get("href", "")
                if not href.startswith(("tg://user?id=", "https://")):
                    return
                attributes = f' href="{escape(href, quote=True)}"'
            self.parts.append(f"<{tag}{attributes}>")
            self.tags.append(tag)

    def handle_endtag(self, tag):
        if not self.cut and tag in self.tags:
            while self.tags:
                current = self.tags.pop()
                self.parts.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, value):
        if self.cut:
            return
        if self.width:
            value = "\n".join(
                "\n".join(wrap(line, self.width, replace_whitespace=False, drop_whitespace=False))
                if line
                else ""
                for line in value.split("\n")
            )
        accepted = []
        for char in value:
            size = units(char)
            if self.used + size > self.limit:
                self.cut = True
                break
            accepted.append(char)
            self.used += size
        self.parts.append(escape("".join(accepted)))

    def result(self):
        if self.cut:
            self.parts.append("…")
        self.parts.extend(f"</{tag}>" for tag in reversed(self.tags))
        return "".join(self.parts)


def compact_html(value, limit=4096, width=46):
    parser = CompactHTML(limit, width)
    parser.feed(value)
    parser.close()
    return parser.result()
