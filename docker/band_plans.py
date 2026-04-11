#!/usr/bin/env python3
"""
IARU Band Plans — Regiones 1, 2 y 3
Fuente: IARU Region 1 HF Band Plan (2016), IARU Region 2 (2020), IARU Region 3 (2021)
Estructura por banda: lista de segmentos (freq_min_khz, freq_max_khz, modos_permitidos)
modos: CW, SSB, RTTY, FT8, FT4, DIGI (genérico), ALL
"""

# ─── Frecuencias FT8/FT4 estándar (globales) ───────────────────────────────
FT8_FREQS = {
    "160m": 1840, "80m": 3573, "60m": 5357, "40m": 7074,
    "30m": 10136, "20m": 14074, "17m": 18100, "15m": 21074,
    "12m": 24915, "10m": 28074, "6m": 50313, "4m": 70154,
    "2m": 144174, "70cm": 432174,
}
FT4_FREQS = {
    "160m": 1838, "80m": 3568, "40m": 7047, "30m": 10140,
    "20m": 14080, "17m": 18104, "15m": 21140, "12m": 24919,
    "10m": 28180, "6m": 50318,
}

# ─── Helper: rango FT8/FT4 ±1 kHz ─────────────────────────────────────────
def _ft(khz): return (khz - 1, khz + 1)

# ═══════════════════════════════════════════════════════════════════════════
#  IARU REGION 1  (Europa, África, Oriente Medio, Asia del Norte)
# ═══════════════════════════════════════════════════════════════════════════
IARU_R1 = {
    "160m": {
        "range": (1810, 2000),
        "segments": [
            (1810, 1838, ["CW"]),
            (1838, 1840, ["FT8","DIGI"]),
            (1840, 1843, ["FT8","FT4","DIGI"]),
            (1843, 1850, ["DIGI"]),
            (1850, 2000, ["CW","SSB","ALL"]),
        ]
    },
    "80m": {
        "range": (3500, 3800),
        "segments": [
            (3500, 3570, ["CW"]),
            (3568, 3572, ["FT4","DIGI"]),
            (3570, 3600, ["DIGI","RTTY"]),
            (3573, 3577, ["FT8","DIGI"]),
            (3600, 3700, ["CW","SSB","ALL"]),
            (3700, 3800, ["CW","SSB","ALL"]),
        ]
    },
    "60m": {
        "range": (5351, 5367),
        "segments": [
            (5351, 5354, ["CW","DIGI"]),
            (5354, 5366, ["SSB","CW","DIGI"]),
            (5357, 5358, ["FT8","DIGI"]),
            (5366, 5367, ["SSB"]),
        ]
    },
    "40m": {
        "range": (7000, 7200),
        "segments": [
            (7000, 7040, ["CW"]),
            (7040, 7050, ["DIGI","RTTY"]),
            (7047, 7052, ["FT4","DIGI"]),
            (7074, 7076, ["FT8","DIGI"]),
            (7050, 7053, ["DIGI"]),
            (7053, 7060, ["DIGI","SSB"]),
            (7060, 7200, ["SSB","CW","ALL"]),
        ]
    },
    "30m": {
        "range": (10100, 10150),
        "segments": [
            (10100, 10130, ["CW"]),
            (10130, 10150, ["DIGI","RTTY"]),
            (10136, 10138, ["FT8","DIGI"]),
            (10140, 10141, ["FT4","DIGI"]),
        ]
    },
    "20m": {
        "range": (14000, 14350),
        "segments": [
            (14000, 14070, ["CW"]),
            (14070, 14099, ["DIGI","RTTY"]),
            (14074, 14076, ["FT8","DIGI"]),
            (14080, 14082, ["FT4","DIGI"]),
            (14099, 14101, ["CW","BEACON"]),
            (14101, 14350, ["SSB","CW","ALL"]),
        ]
    },
    "17m": {
        "range": (18068, 18168),
        "segments": [
            (18068, 18095, ["CW"]),
            (18095, 18109, ["DIGI","RTTY"]),
            (18100, 18102, ["FT8","DIGI"]),
            (18104, 18106, ["FT4","DIGI"]),
            (18109, 18111, ["CW","BEACON"]),
            (18111, 18168, ["SSB","CW","ALL"]),
        ]
    },
    "15m": {
        "range": (21000, 21450),
        "segments": [
            (21000, 21070, ["CW"]),
            (21070, 21110, ["DIGI","RTTY"]),
            (21074, 21076, ["FT8","DIGI"]),
            (21080, 21082, ["FT4","DIGI"]),  # FT4 R1 usa también 21140
            (21110, 21120, ["DIGI","CW"]),
            (21120, 21149, ["CW"]),
            (21149, 21151, ["CW","BEACON"]),
            (21140, 21142, ["FT4","DIGI"]),
            (21151, 21450, ["SSB","CW","ALL"]),
        ]
    },
    "12m": {
        "range": (24890, 24990),
        "segments": [
            (24890, 24915, ["CW"]),
            (24915, 24929, ["DIGI","RTTY"]),
            (24915, 24917, ["FT8","DIGI"]),
            (24919, 24921, ["FT4","DIGI"]),
            (24929, 24931, ["CW","BEACON"]),
            (24931, 24990, ["SSB","CW","ALL"]),
        ]
    },
    "10m": {
        "range": (28000, 29700),
        "segments": [
            (28000, 28070, ["CW"]),
            (28070, 28190, ["DIGI","RTTY"]),
            (28074, 28076, ["FT8","DIGI"]),
            (28180, 28182, ["FT4","DIGI"]),
            (28190, 28225, ["CW","BEACON"]),
            (28225, 29100, ["SSB","CW","ALL"]),
            (29100, 29200, ["FM","ALL"]),
            (29200, 29300, ["ALL"]),
            (29300, 29510, ["SAT","ALL"]),
            (29510, 29700, ["FM","ALL"]),
        ]
    },
    "6m": {
        "range": (50000, 54000),
        "segments": [
            (50000, 50100, ["CW"]),
            (50100, 50300, ["SSB","CW"]),
            (50300, 50400, ["DIGI","CW"]),
            (50313, 50315, ["FT8","DIGI"]),
            (50318, 50320, ["FT4","DIGI"]),
            (50400, 51000, ["ALL"]),
            (51000, 54000, ["ALL"]),
        ]
    },
    "4m": {
        "range": (70000, 70500),
        "segments": [
            (70000, 70100, ["CW"]),
            (70100, 70250, ["SSB","CW"]),
            (70154, 70156, ["FT8","DIGI"]),
            (70250, 70500, ["ALL"]),
        ]
    },
    "2m": {
        "range": (144000, 146000),
        "segments": [
            (144000, 144150, ["CW"]),
            (144150, 144400, ["SSB","CW"]),
            (144174, 144176, ["FT8","DIGI"]),
            (144400, 144490, ["DIGI","RTTY"]),
            (144490, 146000, ["ALL"]),
        ]
    },
    "70cm": {
        "range": (430000, 440000),
        "segments": [
            (430000, 431000, ["ALL"]),
            (432000, 432150, ["CW","SSB"]),
            (432174, 432176, ["FT8","DIGI"]),
            (432150, 432500, ["SSB","CW"]),
            (432500, 440000, ["ALL"]),
        ]
    },
    "23cm": {
        "range": (1240000, 1300000),
        "segments": [
            (1240000, 1243750, ["ALL"]),
            (1296000, 1296150, ["CW","SSB"]),
            (1296150, 1296500, ["SSB","CW"]),
            (1296500, 1300000, ["ALL"]),
        ]
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  IARU REGION 2  (Américas)
# ═══════════════════════════════════════════════════════════════════════════
IARU_R2 = {
    "160m": {
        "range": (1800, 2000),
        "segments": [
            (1800, 1840, ["CW"]),
            (1838, 1840, ["FT8","DIGI"]),
            (1840, 2000, ["SSB","CW","ALL"]),
        ]
    },
    "80m": {
        "range": (3500, 4000),
        "segments": [
            (3500, 3570, ["CW"]),
            (3568, 3572, ["FT4","DIGI"]),
            (3570, 3600, ["DIGI","RTTY"]),
            (3573, 3577, ["FT8","DIGI"]),
            (3600, 3700, ["SSB","CW","ALL"]),
            (3700, 4000, ["SSB","CW","ALL"]),
        ]
    },
    "60m": {
        "range": (5332, 5405),
        "segments": [
            (5332, 5335, ["USB","CW"]),
            (5346, 5350, ["USB","CW"]),
            (5357, 5358, ["FT8","DIGI"]),
            (5358, 5362, ["USB","CW"]),
            (5373, 5377, ["USB","CW"]),
            (5403, 5406, ["USB","CW"]),
        ]
    },
    "40m": {
        "range": (7000, 7300),
        "segments": [
            (7000, 7025, ["CW"]),
            (7025, 7040, ["CW","DIGI"]),
            (7047, 7052, ["FT4","DIGI"]),
            (7040, 7080, ["DIGI","RTTY"]),
            (7074, 7076, ["FT8","DIGI"]),
            (7080, 7300, ["SSB","CW","ALL"]),
        ]
    },
    "30m": {
        "range": (10100, 10150),
        "segments": [
            (10100, 10130, ["CW"]),
            (10130, 10150, ["DIGI","RTTY"]),
            (10136, 10138, ["FT8","DIGI"]),
            (10140, 10141, ["FT4","DIGI"]),
        ]
    },
    "20m": {
        "range": (14000, 14350),
        "segments": [
            (14000, 14070, ["CW"]),
            (14070, 14100, ["DIGI","RTTY"]),
            (14074, 14076, ["FT8","DIGI"]),
            (14080, 14082, ["FT4","DIGI"]),
            (14100, 14350, ["SSB","CW","ALL"]),
        ]
    },
    "17m": {
        "range": (18068, 18168),
        "segments": [
            (18068, 18100, ["CW"]),
            (18100, 18110, ["DIGI","RTTY"]),
            (18100, 18102, ["FT8","DIGI"]),
            (18104, 18106, ["FT4","DIGI"]),
            (18110, 18168, ["SSB","CW","ALL"]),
        ]
    },
    "15m": {
        "range": (21000, 21450),
        "segments": [
            (21000, 21070, ["CW"]),
            (21070, 21100, ["DIGI","RTTY"]),
            (21074, 21076, ["FT8","DIGI"]),
            (21140, 21142, ["FT4","DIGI"]),
            (21100, 21450, ["SSB","CW","ALL"]),
        ]
    },
    "12m": {
        "range": (24890, 24990),
        "segments": [
            (24890, 24920, ["CW"]),
            (24915, 24917, ["FT8","DIGI"]),
            (24919, 24921, ["FT4","DIGI"]),
            (24920, 24990, ["SSB","CW","ALL"]),
        ]
    },
    "10m": {
        "range": (28000, 29700),
        "segments": [
            (28000, 28070, ["CW"]),
            (28070, 28200, ["DIGI","RTTY"]),
            (28074, 28076, ["FT8","DIGI"]),
            (28180, 28182, ["FT4","DIGI"]),
            (28200, 29700, ["SSB","CW","FM","ALL"]),
        ]
    },
    "6m": {
        "range": (50000, 54000),
        "segments": [
            (50000, 50100, ["CW"]),
            (50100, 50600, ["SSB","CW","ALL"]),
            (50313, 50315, ["FT8","DIGI"]),
            (50318, 50320, ["FT4","DIGI"]),
            (50600, 54000, ["ALL"]),
        ]
    },
    "2m": {
        "range": (144000, 148000),
        "segments": [
            (144000, 144200, ["CW","SSB"]),
            (144174, 144176, ["FT8","DIGI"]),
            (144200, 148000, ["ALL"]),
        ]
    },
    "70cm": {
        "range": (420000, 450000),
        "segments": [
            (420000, 426000, ["ALL"]),
            (432174, 432176, ["FT8","DIGI"]),
            (426000, 450000, ["ALL"]),
        ]
    },
    "23cm": {
        "range": (1240000, 1300000),
        "segments": [
            (1240000, 1300000, ["ALL"]),
        ]
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  IARU REGION 3  (Asia-Pacífico)
# ═══════════════════════════════════════════════════════════════════════════
IARU_R3 = {
    "160m": {
        "range": (1800, 2000),
        "segments": [
            (1800, 1838, ["CW"]),
            (1838, 1840, ["FT8","DIGI"]),
            (1840, 2000, ["SSB","CW","ALL"]),
        ]
    },
    "80m": {
        "range": (3500, 3900),
        "segments": [
            (3500, 3535, ["CW"]),
            (3535, 3570, ["CW","DIGI"]),
            (3568, 3572, ["FT4","DIGI"]),
            (3570, 3600, ["DIGI","RTTY"]),
            (3573, 3577, ["FT8","DIGI"]),
            (3600, 3900, ["SSB","CW","ALL"]),
        ]
    },
    "60m": {
        "range": (5351, 5367),
        "segments": [
            (5351, 5367, ["CW","SSB","DIGI"]),
            (5357, 5358, ["FT8","DIGI"]),
        ]
    },
    "40m": {
        "range": (7000, 7200),
        "segments": [
            (7000, 7030, ["CW"]),
            (7030, 7040, ["CW","DIGI"]),
            (7040, 7060, ["DIGI","RTTY"]),
            (7047, 7052, ["FT4","DIGI"]),
            (7074, 7076, ["FT8","DIGI"]),
            (7060, 7200, ["SSB","CW","ALL"]),
        ]
    },
    "30m": {
        "range": (10100, 10150),
        "segments": [
            (10100, 10130, ["CW"]),
            (10130, 10150, ["DIGI","RTTY"]),
            (10136, 10138, ["FT8","DIGI"]),
            (10140, 10141, ["FT4","DIGI"]),
        ]
    },
    "20m": {
        "range": (14000, 14350),
        "segments": [
            (14000, 14070, ["CW"]),
            (14070, 14100, ["DIGI","RTTY"]),
            (14074, 14076, ["FT8","DIGI"]),
            (14080, 14082, ["FT4","DIGI"]),
            (14100, 14350, ["SSB","CW","ALL"]),
        ]
    },
    "17m": {
        "range": (18068, 18168),
        "segments": [
            (18068, 18095, ["CW"]),
            (18095, 18110, ["DIGI","RTTY"]),
            (18100, 18102, ["FT8","DIGI"]),
            (18104, 18106, ["FT4","DIGI"]),
            (18110, 18168, ["SSB","CW","ALL"]),
        ]
    },
    "15m": {
        "range": (21000, 21450),
        "segments": [
            (21000, 21070, ["CW"]),
            (21070, 21100, ["DIGI","RTTY"]),
            (21074, 21076, ["FT8","DIGI"]),
            (21140, 21142, ["FT4","DIGI"]),
            (21100, 21450, ["SSB","CW","ALL"]),
        ]
    },
    "12m": {
        "range": (24890, 24990),
        "segments": [
            (24890, 24915, ["CW"]),
            (24915, 24917, ["FT8","DIGI"]),
            (24919, 24921, ["FT4","DIGI"]),
            (24915, 24990, ["DIGI","RTTY","SSB","CW","ALL"]),
        ]
    },
    "10m": {
        "range": (28000, 29700),
        "segments": [
            (28000, 28070, ["CW"]),
            (28070, 28200, ["DIGI","RTTY"]),
            (28074, 28076, ["FT8","DIGI"]),
            (28180, 28182, ["FT4","DIGI"]),
            (28200, 29700, ["SSB","CW","FM","ALL"]),
        ]
    },
    "6m": {
        "range": (50000, 54000),
        "segments": [
            (50000, 50100, ["CW"]),
            (50100, 50500, ["SSB","CW","ALL"]),
            (50313, 50315, ["FT8","DIGI"]),
            (50318, 50320, ["FT4","DIGI"]),
            (50500, 54000, ["ALL"]),
        ]
    },
    "2m": {
        "range": (144000, 146000),
        "segments": [
            (144000, 144150, ["CW"]),
            (144150, 144400, ["SSB","CW"]),
            (144174, 144176, ["FT8","DIGI"]),
            (144400, 146000, ["ALL"]),
        ]
    },
    "70cm": {
        "range": (430000, 440000),
        "segments": [
            (430000, 432000, ["ALL"]),
            (432174, 432176, ["FT8","DIGI"]),
            (432000, 440000, ["ALL"]),
        ]
    },
    "23cm": {
        "range": (1240000, 1300000),
        "segments": [
            (1240000, 1300000, ["ALL"]),
        ]
    },
}

# ─── Mapa zona -> plan ─────────────────────────────────────────────────────
BAND_PLANS = {1: IARU_R1, 2: IARU_R2, 3: IARU_R3}

# ─── Orden canónico de bandas ─────────────────────────────────────────────
BAND_ORDER = [
    "160m","80m","60m","40m","30m","20m","17m","15m","12m","10m",
    "6m","4m","2m","70cm","23cm"
]

# ─── Todas las bandas disponibles (unión R1+R2+R3) ───────────────────────
ALL_BANDS = list(dict.fromkeys(
    b for plan in BAND_PLANS.values() for b in plan
    if b in BAND_ORDER
))
ALL_BANDS.sort(key=lambda b: BAND_ORDER.index(b) if b in BAND_ORDER else 99)

# ─── Modos disponibles ────────────────────────────────────────────────────
ALL_MODES = ["CW", "SSB", "RTTY", "FT8", "FT4"]

def get_band_range_khz(banda, region=1):
    """Devuelve (min_khz, max_khz) para una banda en una región."""
    plan = BAND_PLANS.get(region, IARU_R1)
    if banda in plan:
        return plan[banda]["range"]
    # fallback: buscar en otras regiones
    for r in [1,2,3]:
        p = BAND_PLANS[r]
        if banda in p:
            return p[banda]["range"]
    return None

def freq_khz_to_band(freq_khz, region=1):
    """Convierte frecuencia kHz a nombre de banda según plan de región."""
    plan = BAND_PLANS.get(region, IARU_R1)
    for banda in BAND_ORDER:
        if banda in plan:
            lo, hi = plan[banda]["range"]
            if lo <= freq_khz <= hi:
                return banda
    return None

def is_cw_segment(freq_khz, region=1):
    """True si la frecuencia está en segmento exclusivo CW de la región."""
    plan = BAND_PLANS.get(region, IARU_R1)
    for banda in BAND_ORDER:
        if banda not in plan: continue
        lo, hi = plan[banda]["range"]
        if not (lo <= freq_khz <= hi): continue
        for seg_lo, seg_hi, modos in plan[banda]["segments"]:
            if seg_lo <= freq_khz <= seg_hi:
                if modos == ["CW"]:
                    return True
    return False

def infer_mode_by_freq(freq_khz, region=1):
    """
    Infiere modo según plan de banda de la región.
    Prioridad: FT4 > FT8 > RTTY/DIGI > CW > SSB
    """
    plan = BAND_PLANS.get(region, IARU_R1)
    for banda in BAND_ORDER:
        if banda not in plan: continue
        lo, hi = plan[banda]["range"]
        if not (lo <= freq_khz <= hi): continue
        best = None
        for seg_lo, seg_hi, modos in plan[banda]["segments"]:
            if seg_lo <= freq_khz <= seg_hi:
                if "FT4" in modos: return "FT4"
                if "FT8" in modos: return "FT8"
                if "RTTY" in modos or "DIGI" in modos:
                    best = "RTTY"
                elif best is None:
                    if "CW" in modos and "SSB" not in modos: best = "CW"
                    elif "SSB" in modos: best = "SSB"
        return best or "SSB"
    return None

