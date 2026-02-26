# bundle_catalog.py
"""
Static per-game bundle → character-code mapping.

Fill in each game's list with ("bundle_stem", "char_code") tuples:
  bundle_stem  — filename without extension, e.g. "a001"
  char_code    — short identifier used for the cache folder, e.g. "avi"

When a game's list is non-empty, the scanner uses it directly (fast — no
bundle files are opened just to discover character names).
When a game's list is empty, the scanner falls back to reading each bundle
file to detect the character code dynamically.
"""

import os

BUNDLE_CATALOG: dict = {
    "PARANORMASIGHT": [
        ("a001", "Ayame Tono"),
        ("a002", "Hideki Araishi"),
        ("a003", "Harue Shigima"),
        ("a004", "Hitomi Okuda"),
        ("a005", "Jun Erio"),
        ("a006", "Kouhei Jonouchi"),
        ("a007", "Makoto Ashimiya"),
        ("a008", "Mio Kurosuzu"),
        ("a009", "Mayu Chozawa"),
        ("a010", "Richter Kai"),
        ("a011", "Storyteller"),
        ("a012", "Shogo Okiie"),
        ("a013", "Takumi Yumioka"),
        ("a014", "Tetsuo Tsutsumi"),
        ("a015", "Yakko Sakazaki"),
        ("a016", "Yoko Fukunaga"),
        ("a017", "Yutaro Namigaki"),
        ("a018", "Hajime Yoshimi"),
        ("a019", "Michiyo Shiraishi")
    ],
    "PARANORMASIGHT_2": [
        ("a001", "Arnav Barnum"),
        ("a002", "Azami Kumoi"),
        ("a003", "Circe Lunarlight"),
        ("a004", "Storyteller"),
        ("a005", "Sodo Kiryu"),
        ("a006", "Shinobu Wakamura"),
        ("a007", "Sato Shiranami"),
        ("a008", "Shotaro Wakamura"),
        ("a009", "Shogo Okiie (unused)"),
        ("a010", "Tsukasa Awao"),
        ("a011", "Tsuyu Minakuchi"),
        ("a012", "Yumeko Shiki"),
        ("a013", "Yuza Minakuchi"),
        ("a014", "Kikuko Tsutsui"),
        ("a015", "Chie Toyama"),
        ("a016", "Kippei Ikoma"),
        ("a017", "Masaru Ide"),
        ("a018", "Yoshiatsu Yamashina"),
        ("a050", "Azusa Somekawa"),
        ("a051", "Kikuko Tsutsui (unused)"),
        ("a052", "Sobae")
    ],
}


def game_key_for_path(streaming_assets_path: str) -> str | None:
    """
    Derive the game key from a StreamingAssets path by finding the *_Data
    component and stripping the _Data suffix.

    e.g. ".../PARANORMASIGHT_2/PARANORMASIGHT_2_Data/StreamingAssets/"
         → "PARANORMASIGHT_2"
    Returns None if no *_Data component is found.
    """
    parts = os.path.normpath(streaming_assets_path).replace("\\", "/").split("/")
    for part in parts:
        if part.endswith("_Data"):
            return part[: -len("_Data")]
    return None
