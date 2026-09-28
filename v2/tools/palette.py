"""Story Scout Next v2 "Peak Arcade" palette.

Six owner base colours, expanded only by mixing base colours with each other
(or deepening toward black / lifting toward white), so every tone stays in
the family. v2/PALETTE.md documents usage; css/style.css mirrors these as
custom properties. Keep all three in sync.
"""

BASE = {
    "space": "#012641",   # Deep Space Blue  - dark base
    "burg": "#90202C",    # Burgundy         - secondary dark
    "indigo": "#432371",  # Indigo Velvet    - mid tone
    "ant": "#F7E6D2",     # Antique White    - light surface
    "sandy": "#FAAE7B",   # Sandy Brown      - warm accent
    "rasp": "#EE005A",    # Raspberry Red    - hot accent
}

P = {
    # Space ramp (dark base)
    "void": "#000B14",        # space x black 70% - outline ink
    "space-950": "#00111D",   # space x black 55%
    "space-900": "#011B2E",   # space x black 30%
    "space-800": "#012641",   # BASE
    "space-700": "#12254D",   # space x indigo 25%
    "space-600": "#2D495B",   # space x antique 18%
    "space-500": "#576974",   # space x antique 35%
    # Indigo ramp (mid tone)
    "indigo-900": "#1F2557",  # indigo x space 55%
    "indigo-800": "#2F2463",  # indigo x space 30%
    "indigo-700": "#432371",  # BASE
    "indigo-600": "#634682",  # indigo x antique 18%
    "indigo-500": "#826793",  # indigo x antique 35%
    "indigo-300": "#AF98AB",  # indigo x antique 60% ("haze")
    # Burgundy ramp (secondary dark)
    "burg-900": "#3A2439",    # burgundy x space 60%
    "burg-800": "#652232",    # burgundy x space 30%
    "burg-700": "#90202C",    # BASE
    "burg-600": "#B1153C",    # burgundy x raspberry 35%
    # Raspberry ramp (hot accent)
    "rasp-700": "#C80D48",    # raspberry x burgundy 40%
    "rasp-600": "#EE005A",    # BASE
    "rasp-400": "#F1457E",    # raspberry x antique 30%
    "rasp-200": "#F48FA4",    # raspberry x antique 62%
    # Sandy ramp (warm accent)
    "sandy-800": "#C06050",   # sandy x burgundy 55%
    "sandy-700": "#DA8363",   # sandy x burgundy 30%
    "sandy-600": "#FAAE7B",   # BASE
    "sandy-400": "#F9C49E",   # sandy x antique 40%
    "sandy-200": "#F8D5B8",   # sandy x antique 70%
    # Antique ramp (light surface)
    "ant-25": "#FEFCFA",      # antique x white 90% (day cards)
    "ant-50": "#FBF4EB",      # antique x white 55%
    "ant-100": "#F7E6D2",     # BASE
    "ant-200": "#F8D8BC",     # antique x sandy 25%
    "ant-300": "#D7C3C1",     # antique x indigo 18%
    # Scene bridges (two bases mixed 50/50-ish)
    "dusk": "#871568",        # indigo x raspberry 40%
    "mauve": "#6A224E",       # indigo x burgundy 50%
    "ember": "#C56754",       # burgundy x sandy 50%
}
