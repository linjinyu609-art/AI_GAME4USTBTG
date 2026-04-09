from __future__ import annotations

from typing import Iterable

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}

RARITY_COLOR = {
    "R": COLORS["white"],
    "SR": COLORS["cyan"],
    "SSR": COLORS["magenta"],
}

RANK_COLOR = {
    "Normal": COLORS["white"],
    "Elite": COLORS["yellow"],
    "Boss": COLORS["red"],
}


def supports_color() -> bool:
    return True


def color(text: str, tone: str, bold: bool = False) -> str:
    if not supports_color():
        return text
    prefix = COLORS.get(tone, "")
    if bold:
        prefix = BOLD + prefix
    return f"{prefix}{text}{RESET}"


def rarity(text: str, rar: str) -> str:
    if not supports_color():
        return text
    return f"{RARITY_COLOR.get(rar, COLORS['white'])}{text}{RESET}"


def rank(text: str, rk: str) -> str:
    if not supports_color():
        return text
    return f"{RANK_COLOR.get(rk, COLORS['white'])}{text}{RESET}"


def line(char: str = "=", width: int = 72) -> str:
    return char * width


def title(text: str, width: int = 72) -> str:
    body = f" {text} "
    pad = max(0, width - len(body))
    left = pad // 2
    right = pad - left
    return f"{line('=', left)}{BOLD}{body}{RESET}{line('=', right)}"


def section(text: str) -> str:
    return f"\n{color(text, 'yellow', bold=True)}"


def kv(items: Iterable[tuple[str, str]]) -> str:
    rows = [f"{DIM}{k}:{RESET} {v}" for k, v in items]
    return " | ".join(rows)


def progress(current: int, target: int, width: int = 20) -> str:
    if target <= 0:
        target = 1
    ratio = max(0.0, min(1.0, current / target))
    fill = int(width * ratio)
    bar = "█" * fill + "░" * (width - fill)
    pct = int(ratio * 100)
    tone = "green" if ratio >= 1.0 else "cyan"
    return f"{color(bar, tone)} {current}/{target} ({pct}%)"


def menu_block(lines: list[str]) -> str:
    top = line("-")
    body = "\n".join(f"  {item}" for item in lines)
    return f"{top}\n{body}\n{top}"


def card_block(name: str, subtitle: str, lines: list[str], width: int = 56) -> str:
    header = f"[{name}] {subtitle}"[: width - 4]
    out = ["+" + "-" * (width - 2) + "+", f"| {header.ljust(width - 4)} |", "+" + "-" * (width - 2) + "+"]
    for l in lines:
        out.append(f"| {l[: width - 4].ljust(width - 4)} |")
    out.append("+" + "-" * (width - 2) + "+")
    return "\n".join(out)
