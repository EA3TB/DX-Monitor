#!/usr/bin/env python3
"""DX Monitor Docker — v13 — proceso único (monitor + web)"""

import xml.etree.ElementTree as ET
import socket, time, logging, glob, os, re, datetime, zoneinfo, json, threading, math, queue
from collections import defaultdict
import requests
from flask import Flask, jsonify, render_template, request, Response, stream_with_context
from log_readers import (
    leer_hrd_xml, leer_swisslog_mdb, leer_log4om_sqlite, leer_adif
)
from band_plans import (
    ALL_BANDS, ALL_MODES,
    freq_khz_to_band, is_cw_segment, infer_mode_by_freq,
    FT8_FREQS, FT4_FREQS
)

VERSION     = "v13"
CONFIG_PATH = "/opt/dx_monitor_docker/config.json"
FLAGS_PATH  = "/opt/dx_monitor_docker/flags.json"
STATUS_PATH = "/opt/dx_monitor_docker/status.json"
LOG_PATH    = "/opt/dx_monitor_docker/dx_monitor.log"
CTY_PATH    = "/opt/dx_monitor_docker/cty.dat"

CONFIG_DEFAULTS = {
    "callsign":"","locator":"","qth_lat":0.0,"qth_lon":0.0,
    "log_type":"hrd_xml",        # hrd_xml | swisslog_mdb | log4om_sqlite | adif
    "log_path":"",               # path al fichero de log (MDB/SQLite/ADIF)
    "hrd_xml_dir":"","hrd_xml_glob":"*.xml",
    "cluster_host":"","cluster_port":7300,
    "cluster_login":"","cluster_password":"",
    "telegram_token":"","telegram_chat_id":"",
    "timezone":"Europe/Madrid","alert_lang":"es","time_mode":"local",
    "log_refresh_minutes":1,
}

FLAGS_DEFAULT = {
    "pais_nuevo":True,"pais_trabajado":True,"banda_nueva":True,"banda_sin_qsl":False,
    "modo_nuevo":True,"modo_sin_qsl":False,
    "bandas_activas":ALL_BANDS[:],"modos_activos":ALL_MODES[:],"iaru_region":1,
}

# ── Logging ───────────────────────────────────────────────────────────────────
import logging.handlers

class LocalTimezoneFormatter(logging.Formatter):
    """Formatter que usa la timezone configurada en config.json."""
    def formatTime(self, record, datefmt=None):
        try:
            import json, zoneinfo
            with open(CONFIG_PATH,"r") as f: cfg = json.load(f)
            tz = zoneinfo.ZoneInfo(cfg.get("timezone","UTC"))
        except:
            tz = datetime.timezone.utc
        ct = datetime.datetime.fromtimestamp(record.created, tz=tz)
        if datefmt:
            return ct.strftime(datefmt)
        return ct.strftime("%Y-%m-%d %H:%M:%S")

log = logging.getLogger("dxmonitor")
log.setLevel(logging.INFO)
fmt = LocalTimezoneFormatter("%(asctime)s [%(levelname)s] %(message)s")
_ch = logging.StreamHandler(); _ch.setFormatter(fmt); log.addHandler(_ch)
_fh = logging.handlers.TimedRotatingFileHandler(
    LOG_PATH, when="W0", interval=1, backupCount=4, encoding="utf-8")
_fh.setFormatter(fmt); log.addHandler(_fh)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ── Regexes spots ─────────────────────────────────────────────────────────────
RE_CC11 = re.compile(r"^CC11\^([\d.]+)\^(\S+)\^[^\^]+\^(\d{4}Z)\^([^\^]*)\^([^\^]+)\^")
RE_RT   = re.compile(r"DX de\s+(\S+?):\s+([\d.]+)\s+(\S+)\s+(.*?)\s+(\d{4}Z)\s*$")
RE_SH   = re.compile(r"^\s*([\d.]+)\s+(\S+)\s+\d{2}-\w{3}-\d{4}\s+(\d{4}Z)\s+(.*?)\s+<(\S+)>\s*$")

# ── Estado global ─────────────────────────────────────────────────────────────
_confirmados = defaultdict(lambda: defaultdict(set))
_trabajados  = defaultdict(lambda: defaultdict(set))
_lock        = threading.Lock()
_alertas_enviadas = set()
_lock_alertas     = threading.Lock()
_pfx_a_dxcc = {}
_pfx_cty    = {}

_status = {
    "version":VERSION,"cluster_host":"","cluster_connected":False,
    "cluster_last_spot":"","dxcc_confirmados":0,"dxcc_trabajados":0,
    "qsos_total":0,"pfx_cty":0,"pfx_tabla":0,"last_alerts":[],
    "log_tail":[],"cty_dat_mtime":"","xml_hrd_path":"",
    "errores":0,"all_bands":ALL_BANDS,"all_modes":ALL_MODES,
    "callsign":"","locator":"","log_source":"hrd_xml",
}
_status_lock = threading.Lock()
_cluster_paused = threading.Event()
_log_load_lock  = threading.Lock()  # evita cargas simultáneas del log

# ── SSE ───────────────────────────────────────────────────────────────────────
_sse_clients = []
_sse_lock    = threading.Lock()

def sse_push(data):
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try: q.put_nowait(data)
            except: dead.append(q)
        for q in dead: _sse_clients.remove(q)

# ── Helpers ───────────────────────────────────────────────────────────────────
HOSTFS = "/hostfs"

def host_path(path):
    if not path: return path
    if path.startswith(HOSTFS): return path
    return HOSTFS + path

def banda_permite_ssb(freq_khz, region=1):
    """True si algún segmento de la frecuencia permite SSB o ALL."""
    from band_plans import BAND_PLANS, BAND_ORDER
    plan = BAND_PLANS.get(region, BAND_PLANS[1])
    for banda in BAND_ORDER:
        if banda not in plan: continue
        lo, hi = plan[banda]["range"]
        if not (lo <= freq_khz <= hi): continue
        for seg_lo, seg_hi, modos in plan[banda]["segments"]:
            if seg_lo <= freq_khz <= seg_hi:
                if any(m in modos for m in ["SSB","ALL","USB"]): return True
        return False
    return True

def maidenhead_to_latlon(grid):
    grid = grid.upper().strip()
    if len(grid) < 4: return None, None
    try:
        lon = (ord(grid[0])-ord('A'))*20-180
        lat = (ord(grid[1])-ord('A'))*10-90
        lon += (ord(grid[2])-ord('0'))*2
        lat += (ord(grid[3])-ord('0'))*1
        if len(grid) >= 6:
            lon += (ord(grid[4])-ord('A'))*5/60
            lat += (ord(grid[5])-ord('A'))*2.5/60
            lon += 2.5/60; lat += 1.25/60
        else:
            lon += 1.0; lat += 0.5
        return round(lat,4), round(lon,4)
    except: return None, None

# ── Config / Flags ────────────────────────────────────────────────────────────
def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp,"w") as f: json.dump(data, f, indent=2)
    os.replace(tmp, path)

def leer_config():
    cfg = dict(CONFIG_DEFAULTS)
    try:
        with open(CONFIG_PATH,"r") as f: datos = json.load(f)
        cfg.update(datos)
    except FileNotFoundError: pass
    except Exception as e: log.warning("Error leyendo config.json: %s", e)
    if cfg.get("locator") and cfg["qth_lat"] == 0.0 and cfg["qth_lon"] == 0.0:
        lat, lon = maidenhead_to_latlon(cfg["locator"])
        if lat: cfg["qth_lat"] = lat; cfg["qth_lon"] = lon
    return cfg

def inicializar_config():
    if not os.path.exists(CONFIG_PATH):
        _write_json(CONFIG_PATH, CONFIG_DEFAULTS)
        log.info("config.json creado con valores por defecto.")
    else:
        try:
            with open(CONFIG_PATH,"r") as f: datos = json.load(f)
            updated = False
            for k, v in CONFIG_DEFAULTS.items():
                if k not in datos: datos[k] = v; updated = True
            if updated:
                _write_json(CONFIG_PATH, datos)
                log.info("config.json migrado.")
        except Exception as e: log.warning("Error migrando config.json: %s", e)

def leer_flags():
    try:
        with open(FLAGS_PATH,"r") as f: datos = json.load(f)
        flags = dict(FLAGS_DEFAULT); flags.update(datos); return flags
    except: return dict(FLAGS_DEFAULT)

def inicializar_flags():
    if not os.path.exists(FLAGS_PATH):
        _write_json(FLAGS_PATH, FLAGS_DEFAULT)
        log.info("flags.json creado.")
    else:
        try:
            with open(FLAGS_PATH,"r") as f: datos = json.load(f)
            updated = False
            for k, v in FLAGS_DEFAULT.items():
                if k not in datos: datos[k] = v; updated = True
            if updated:
                _write_json(FLAGS_PATH, datos)
                log.info("flags.json migrado.")
        except: pass

def _escribir_status():
    tmp = STATUS_PATH + ".tmp"
    try:
        with _status_lock: data = dict(_status)
        with open(tmp,"w") as f: json.dump(data, f, ensure_ascii=False, default=str)
        os.replace(tmp, STATUS_PATH)
        # Notificar a clientes SSE si hay nuevas alertas
        sse_push(json.dumps(data.get("last_alerts",[]), ensure_ascii=False))
    except Exception as e: log.warning("Error escribiendo status.json: %s", e)

def _leer_log_tail(n=40):
    try:
        with open(LOG_PATH,"r",encoding="utf-8",errors="ignore") as f: lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except: return []

# ── Azimut / distancia ────────────────────────────────────────────────────────
def calcular_azimut_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1r = math.radians(lat1); lat2r = math.radians(lat2); dlon = math.radians(lon2-lon1)
    x = math.sin(dlon)*math.cos(lat2r)
    y = math.cos(lat1r)*math.sin(lat2r)-math.sin(lat1r)*math.cos(lat2r)*math.cos(dlon)
    az_sp = math.degrees(math.atan2(x,y))%360; az_lp = (az_sp+180)%360
    a = math.sin((lat2r-lat1r)/2)**2+math.cos(lat1r)*math.cos(lat2r)*math.sin(dlon/2)**2
    dist = R*2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(az_sp), round(az_lp), round(dist)

# ── cty.dat ───────────────────────────────────────────────────────────────────
def actualizar_bigcty(path):
    url = "https://www.country-files.com/bigcty/cty.dat"
    try:
        import urllib.request, email.utils
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote_date = resp.headers.get("Last-Modified","")
        if os.path.exists(path) and remote_date:
            if email.utils.parsedate_to_datetime(remote_date).timestamp() <= os.path.getmtime(path):
                log.info("Big CTY actualizado. No hay nueva version."); return False
        log.info("Descargando nueva version de Big CTY...")
        tmp = path+".tmp"; urllib.request.urlretrieve(url, tmp)
        with open(tmp,'r',errors='ignore') as f: lineas = f.readlines()
        if len(lineas) < 1000:
            log.error("Big CTY incorrecto (%d lineas).", len(lineas)); os.remove(tmp); return False
        os.replace(tmp, path); log.info("Big CTY actualizado: %d lineas.", len(lineas)); return True
    except Exception as e: log.warning("Error al actualizar Big CTY: %s", e); return False

def hilo_actualizar_cty():
    while True:
        time.sleep(86400)
        if actualizar_bigcty(CTY_PATH):
            global _pfx_cty
            _pfx_cty = cargar_cty_dat(CTY_PATH)
            cargar_log()

def cargar_cty_dat(path):
    pfx_cty = {}
    try:
        with open(path,"r",encoding="utf-8",errors="ignore") as f: contenido = f.read()
    except FileNotFoundError: log.error("No se encontro cty.dat en %s", path); return pfx_cty
    texto = " ".join(contenido.splitlines()); bloques = texto.split(";")
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque: continue
        partes = bloque.split(":")
        if len(partes) < 9: continue
        nombre = partes[0].strip()
        try: lat = float(partes[4].strip()); lon = -float(partes[5].strip())
        except: lat = lon = 0.0
        dxcc_pfx = partes[7].strip(); resto = ":".join(partes[8:]).strip()
        lista = [p.strip() for p in resto.split(",") if p.strip()]
        for pfx in [dxcc_pfx]+lista:
            pfx_limpio = pfx.lstrip("=").strip()
            if pfx_limpio: pfx_cty[pfx_limpio] = (nombre, lat, lon)
    log.info("cty.dat cargado: %d prefijos.", len(pfx_cty)); return pfx_cty

def coords_por_call(call):
    partes = call.upper().split("/"); candidatos = [partes[0]]
    if len(partes) > 1 and len(partes[1]) > 1: candidatos.append(partes[1])
    mejor = ("",0.0,0.0); mejor_len = 0
    for c in candidatos:
        for n in range(len(c),0,-1):
            pfx = c[:n]
            if pfx in _pfx_cty:
                if n > mejor_len: mejor_len = n; mejor = _pfx_cty[pfx]
                break
    return mejor

def construir_pfx_a_dxcc(xml_path):
    nombre_a_dxcc = {}; registros_xml = []
    try:
        tree = ET.parse(xml_path); root = tree.getroot()
        registros_xml = root.findall("LogbookBackup/Record")
        for rec in registros_xml:
            a = rec.attrib; dxcc = a.get("COL_DXCC","").strip(); country = a.get("COL_COUNTRY","").strip()
            if not dxcc or not country: continue
            try: dxcc_num = int(dxcc)
            except: continue
            clave = country.lower()[:12]
            if clave not in nombre_a_dxcc: nombre_a_dxcc[clave] = (dxcc_num, country)
    except Exception as e: log.error("Error XML: %s", e); return {}
    pfx_map = {}
    for pfx,(nombre_cty,lat,lon) in _pfx_cty.items():
        clave = nombre_cty.lower()[:12]
        if clave in nombre_a_dxcc: pfx_map[pfx] = (nombre_a_dxcc[clave][0], nombre_cty)
        else:
            clave8 = nombre_cty.lower()[:8]
            for k,(num,nom) in nombre_a_dxcc.items():
                if k[:8] == clave8: pfx_map[pfx] = (num, nombre_cty); break
    for rec in registros_xml:
        a = rec.attrib; dxcc = a.get("COL_DXCC","").strip(); call = a.get("COL_CALL","").strip().upper()
        country = a.get("COL_COUNTRY","").strip()
        if not dxcc or not call or "/" in call: continue
        try: dxcc_num = int(dxcc)
        except: continue
        for n in range(min(4,len(call)),0,-1):
            pfx = call[:n]
            if pfx not in pfx_map: pfx_map[pfx] = (dxcc_num, country)
    log.info("Tabla prefijo->DXCC construida: %d prefijos.", len(pfx_map)); return pfx_map

SUFIJOS_OP = {"P","M","MM","AM","QRP","QRPP","LH","LGT","A","B","C","R","0","1","2","3","4","5","6","7","8","9"}
def es_sufijo_op(s): return s in SUFIJOS_OP or s.isdigit() or (len(s)<=2 and s.isalpha() and s in SUFIJOS_OP)

def call_a_dxcc(call):
    partes = call.upper().split("/")
    if len(partes) == 1: candidatos = [partes[0]]
    elif len(partes) == 2:
        a, d = partes[0], partes[1]
        if es_sufijo_op(d): candidatos = [a]
        elif len(d) < len(a): candidatos = [d]
        elif len(a) < len(d): candidatos = [a]
        else:
            def tid(s): return any(c.isdigit() for c in s[:-1])
            def ml(s):
                for n in range(len(s),0,-1):
                    if s[:n] in _pfx_a_dxcc: return n
                return 0
            if tid(a) and not tid(d): candidatos = [d]
            elif tid(d) and not tid(a): candidatos = [a]
            else: candidatos = [d] if ml(d) >= ml(a) else [a]
    else: candidatos = [partes[0]]
    mn = 0; mnom = ""; ml2 = 0; mlat = 0.0; mlon = 0.0
    for c in candidatos:
        for n in range(len(c),0,-1):
            pfx = c[:n]
            if pfx in _pfx_a_dxcc:
                if n > ml2: ml2 = n; mn,mnom = _pfx_a_dxcc[pfx]; _,mlat,mlon = _pfx_cty.get(pfx,("",0.0,0.0))
                break
        for n in range(len(c),0,-1):
            pfx = c[:n]
            if pfx in _pfx_cty:
                if n > ml2:
                    ncty,lcty,locty = _pfx_cty[pfx]
                    for k,(nk,nomk) in _pfx_a_dxcc.items():
                        if nomk.lower()[:8] == ncty.lower()[:8]:
                            ml2 = n; mn = nk; mnom = ncty; mlat = lcty; mlon = locty; break
                break
    if not mn: return 0,"",0.0,0.0
    if mlat == 0.0 and mlon == 0.0: _,mlat,mlon = coords_por_call(call)
    return mn, mnom, mlat, mlon

# ── XML HRD ───────────────────────────────────────────────────────────────────
def normalizar_modo(m):
    m = m.upper().strip()
    if re.search(r"FT\s*8",m): return "FT8"
    if re.search(r"FT\s*4",m): return "FT4"
    if "MFSK" in m: return "FT4"
    if "RTTY" in m or "PSK" in m or "BPSK" in m: return "RTTY"
    if m in ("USB","LSB","SSB","AM","FM","PHONE"): return "SSB"
    if m in ("CW","CW-R"): return "CW"
    if re.search(r"^[+-]\d{2}\b",m): return "FT8"
    if re.search(r"\b[+-]\d{2}\s*(DB|DBM)?\b",m): return "FT8"
    return m

def cargar_log_hrd():
    """Compatibilidad: llama a cargar_log()"""
    cargar_log()

def _limpiar_stats_log():
    """Limpia estadísticas, _confirmados, _trabajados y _pfx_a_dxcc.
    Garantiza que no se envíen alertas con datos de un log anterior."""
    global _confirmados, _trabajados, _pfx_a_dxcc
    from collections import defaultdict
    with _lock:
        _confirmados = defaultdict(lambda: defaultdict(set))
        _trabajados  = defaultdict(lambda: defaultdict(set))
    _pfx_a_dxcc = {}
    with _status_lock:
        _status["dxcc_confirmados"] = 0; _status["dxcc_trabajados"] = 0
        _status["qsos_total"] = 0;       _status["pfx_tabla"] = 0
        _status["xml_hrd_path"] = "";    _status["log_source"] = ""
    _escribir_status()

def cargar_log():
    """Carga el log del usuario según log_type configurado.
    Usa _log_load_lock para evitar cargas simultáneas."""
    cfg = leer_config()
    if cfg.get("log_type","hrd_xml") != "hrd_xml":
        _construir_pfx_a_dxcc_desde_cty()
    if not _log_load_lock.acquire(blocking=False):
        log.info("Log load already in progress, skipping.")
        return
    try:
        _cargar_log_impl()
    finally:
        _log_load_lock.release()

def _cargar_log_impl():
    global _confirmados, _trabajados, _pfx_a_dxcc
    cfg      = leer_config()
    log_type = cfg.get("log_type", "hrd_xml")
    log_path = cfg.get("log_path", "")

    cn = tn = stats = None

    if log_type == "hrd_xml":
        xml_dir = cfg.get("hrd_xml_dir","") or log_path
        if not xml_dir:
            log.error("XML directory not configured."); _limpiar_stats_log(); return
        cn, tn, stats, registros, path = leer_hrd_xml(
            xml_dir, cfg.get("hrd_xml_glob","*.xml"), host_path_fn=host_path)
        if cn is None: _limpiar_stats_log(); return
        _pfx_a_dxcc = construir_pfx_a_dxcc(path)

    elif log_type == "swisslog_mdb":
        mdb_real = host_path(log_path) if log_path else ""
        if not mdb_real:
            log.error("Log path not configured."); _limpiar_stats_log(); return
        _construir_pfx_a_dxcc_desde_cty()
        cn, tn, stats = leer_swisslog_mdb(mdb_real, pfx_a_dxcc=_pfx_a_dxcc)
        if cn is None: _limpiar_stats_log(); return

    elif log_type == "log4om_sqlite":
        db_real = host_path(log_path) if log_path else ""
        if not db_real:
            log.error("Log path not configured."); _limpiar_stats_log(); return
        _construir_pfx_a_dxcc_desde_cty()
        cn, tn, stats = leer_log4om_sqlite(db_real)
        if cn is None: _limpiar_stats_log(); return

    elif log_type == "adif":
        adif_real = host_path(log_path) if log_path else ""
        if not adif_real:
            log.error("Log path not configured."); _limpiar_stats_log(); return
        _construir_pfx_a_dxcc_desde_cty()
        cn, tn, stats = leer_adif(adif_real)
        if cn is None: _limpiar_stats_log(); return

    else:
        log.error("Unknown log type: %s", log_type); _limpiar_stats_log(); return

    with _lock: _confirmados = cn; _trabajados = tn
    log.info("Log loaded: %d DXCC confirmed, %d worked.", len(cn), len(tn))
    cty_mtime = ""
    try: cty_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(CTY_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    except: pass
    with _status_lock:
        _status["dxcc_confirmados"] = len(cn); _status["dxcc_trabajados"] = len(tn)
        _status["qsos_total"]    = stats.get("qsos_total",0)
        _status["pfx_tabla"]     = len(_pfx_a_dxcc)
        _status["pfx_cty"]       = len(_pfx_cty)
        _status["xml_hrd_path"]  = stats.get("xml_hrd_path","")
        _status["log_source"]    = stats.get("log_source","hrd_xml")
        _status["cty_dat_mtime"] = cty_mtime
        cfg2 = leer_config()
        _status["callsign"] = cfg2.get("callsign",""); _status["locator"] = cfg2.get("locator","")
    _escribir_status()

def _construir_pfx_a_dxcc_desde_cty():
    """Construye _pfx_a_dxcc desde _pfx_cty para tipos no-HRD.
    Solo reconstruye si _pfx_a_dxcc está vacío — evita log repetido.
    Las claves se normalizan a MAYÚSCULAS para coincidir con P_DXCC de Swisslog."""
    global _pfx_a_dxcc
    if not _pfx_cty: return
    if _pfx_a_dxcc:  # ya construido — no reconstruir ni loguear
        return
    nombre_a_num = {}; counter = 1; pfx_map = {}
    for pfx, (nombre, lat, lon) in _pfx_cty.items():
        if nombre not in nombre_a_num:
            nombre_a_num[nombre] = counter; counter += 1
        # Claves en MAYÚSCULAS — Swisslog P_DXCC siempre está en mayúsculas
        pfx_map[pfx.upper()] = (nombre_a_num[nombre], nombre)
    _pfx_a_dxcc = pfx_map
    log.info("Prefix->DXCC table built from cty.dat: %d prefixes.", len(pfx_map))

# ── Cluster ───────────────────────────────────────────────────────────────────
def extraer_propagacion(c):
    sp = re.search(r"\[SP:(\d+)",c); lp = re.search(r"LP:(\d+)",c)
    r = {}
    if sp: r["sp"] = int(sp.group(1))
    if lp: r["lp"] = int(lp.group(1))
    return r

def limpiar_comment(c):
    c = re.sub(r"\[SP:\d+(?:,LP:\d+)?\]","",c)
    c = re.sub(r"\[LP:\d+\]","",c); c = re.sub(r"\[0\]","",c); return c.strip()

_TG = {
    "es":{"pais_nuevo":"PAÍS NUEVO","pais_trabajado":"PAÍS TRABAJADO","banda_nueva":"BANDA NUEVA",
          "banda_sin_qsl":"BANDA SIN QSL","modo_nuevo":"MODO NUEVO","modo_sin_qsl":"MODO SIN QSL",
          "spotter":"Spotter","propagacion":"Propagacion"},
    "en":{"pais_nuevo":"NEW COUNTRY","pais_trabajado":"WORKED COUNTRY","banda_nueva":"NEW BAND",
          "banda_sin_qsl":"BAND NO QSL","modo_nuevo":"NEW MODE","modo_sin_qsl":"MODE NO QSL",
          "spotter":"Spotter","propagacion":"Propagation"},
}
def tg_label(key, lang="es"): return _TG.get(lang, _TG["es"]).get(key, key)

def clasificar_spot(dxcc_num, banda, modo, flags):
    with _lock: conf = _confirmados; trab = _trabajados
    if dxcc_num not in trab:
        if flags.get("pais_nuevo",True): return "pais_nuevo","🌍"
    elif dxcc_num not in conf:
        if flags.get("pais_trabajado",True): return "pais_trabajado","🔄"
    elif banda not in conf[dxcc_num]:
        if banda not in trab[dxcc_num]:
            if flags.get("banda_nueva",True): return "banda_nueva","📡"
        elif flags.get("banda_sin_qsl",False): return "banda_sin_qsl","📡"
    elif modo not in conf[dxcc_num][banda]:
        if modo not in trab[dxcc_num].get(banda,set()):
            if flags.get("modo_nuevo",True): return "modo_nuevo","🔊"
        elif flags.get("modo_sin_qsl",False): return "modo_sin_qsl","🔊"
    return None, None

def procesar_linea(linea):
    global _alertas_enviadas
    mc = RE_CC11.match(linea)
    if mc:
        freq = float(mc.group(1)); freq = freq/1000 if freq > 1000 else freq
        call = mc.group(2).upper().strip(); hora = mc.group(3)
        comment = mc.group(4).strip(); spotter = mc.group(5).strip()
    else:
        m = RE_RT.search(linea)
        if m:
            spotter = m.group(1).rstrip(":"); freq = float(m.group(2))
            call = m.group(3).upper().strip(); comment = m.group(4).strip(); hora = m.group(5)
        else:
            m2 = RE_SH.search(linea)
            if not m2: return
            freq = float(m2.group(1)); freq = freq/1000 if freq > 1000 else freq
            call = m2.group(2).upper().strip(); hora = m2.group(3)
            comment = m2.group(4).strip(); spotter = m2.group(5)

    flags = leer_flags(); cfg = leer_config()
    region = int(flags.get("iaru_region",1))
    bandas_activas = flags.get("bandas_activas", FLAGS_DEFAULT["bandas_activas"])
    modos_activos  = flags.get("modos_activos",  FLAGS_DEFAULT["modos_activos"])
    lang = cfg.get("alert_lang","es")

    freq_khz = freq*1000
    banda = freq_khz_to_band(freq_khz, region)
    if not banda or banda not in bandas_activas: return

    prop = extraer_propagacion(comment); clean = limpiar_comment(comment)
    modo = normalizar_modo(clean)
    modo_explicito = modo in ["CW","SSB","RTTY","FT8","FT4"]

    if not modo_explicito:
        # Comprobar si la frecuencia coincide con una frecuencia estándar FT8/FT4 (±1 kHz)
        freq_mhz = freq_khz / 1000
        ft8_match = any(abs(freq_mhz - f/1000) <= 0.001 for f in FT8_FREQS.values())
        ft4_match = any(abs(freq_mhz - f/1000) <= 0.001 for f in FT4_FREQS.values())
        if ft4_match:
            modo = "FT4"
        elif ft8_match:
            modo = "FT8"
        else:
            # Para CW/SSB inferir por frecuencia; RTTY solo si está en el comentario
            inferido = infer_mode_by_freq(freq_khz, region) or "SSB"
            if inferido in ["RTTY","FT8","FT4"]:
                # Si la banda no permite SSB, usar CW como fallback
                inferido = "SSB" if banda_permite_ssb(freq_khz, region) else "CW"
            modo = inferido

    if is_cw_segment(freq_khz, region) and modo not in ["SSB","RTTY","FT8","FT4"]:
        modo = "CW"
    if modo not in modos_activos: return

    dxcc_num, nombre, dx_lat, dx_lon = call_a_dxcc(call)
    if not dxcc_num:
        log.info("SPOT sin DXCC: %s %.3f %s/%s", call, freq, banda, modo); return

    ahora = time.time()
    with _lock_alertas:
        _alertas_enviadas = {(c,b,mo,t) for c,b,mo,t in _alertas_enviadas if ahora-t < 600}
        if any(c==call and b==banda and mo==modo for c,b,mo,t in _alertas_enviadas): return

    tipo, icono = clasificar_spot(dxcc_num, banda, modo, flags)
    log.info("SPOT %s [%d] %s %s/%s -> %s", call, dxcc_num, nombre, banda, modo, tipo or "YA_CONFIRMADO")
    if not tipo: return

    with _lock_alertas: _alertas_enviadas.add((call, banda, modo, ahora))
    log.info("ALERTA %s: %s [%d] %s %s/%s", tipo, call, dxcc_num, nombre, banda, modo)

    qth_lat = cfg.get("qth_lat",0.0); qth_lon = cfg.get("qth_lon",0.0)
    if qth_lat == 0.0:
        lat, lon = maidenhead_to_latlon(cfg.get("locator",""))
        if lat: qth_lat, qth_lon = lat, lon
    az_sp, az_lp, dist = calcular_azimut_distancia(qth_lat, qth_lon, dx_lat, dx_lon)
    prop_str = formatear_propagacion(prop)

    time_mode = cfg.get("time_mode","local")
    if time_mode == "utc":
        hora_str   = hora.replace("Z","") + " UTC"
        hora_label = "UTC Time" if lang=="en" else "Hora UTC"
    else:
        hora_str   = utc_a_local(hora, cfg.get("timezone","Europe/Madrid"))
        hora_label = "Local time" if lang=="en" else "Hora local"

    titulo = tg_label(tipo, lang)
    msg = ("📢 <b>%s</b>  —  %s\n📻 %.3f MHz  •  %s\n%s <b>%s — %s/%s</b>\n"
           "👁 %s: %s\n🕐 %s: %s\n🧭 Az SP: %d°  |  LP: %d°  |  %d km") % (
        call, nombre, freq, modo, icono, titulo, banda, modo,
        tg_label("spotter",lang), spotter, hora_label, hora_str, az_sp, az_lp, dist)
    if clean:    msg += "\n📝 %s" % clean
    if prop_str: msg += "\n📶 %s: %s" % (tg_label("propagacion",lang), prop_str)

    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%H:%M:%S")
    now_date = now_dt.strftime("%d/%m/%Y")
    entry = {"ts":now_str,"call":call,"dxcc":nombre,"freq":"%.3f"%freq,
             "banda":banda,"modo":modo,"tipo":tipo,"icono":icono,"spotter":spotter,"date":now_date}
    with _status_lock:
        _status["cluster_last_spot"] = now_str
        _status["last_alerts"].insert(0, entry)
        _status["last_alerts"] = _status["last_alerts"][:10]
        _status["log_tail"] = _leer_log_tail()
    _escribir_status()
    enviar_telegram(msg, cfg)

def formatear_propagacion(prop):
    if not prop: return ""
    p = []
    if "sp" in prop: p.append("SP %d%%" % prop["sp"])
    if "lp" in prop: p.append("LP %d%%" % prop["lp"])
    return " | ".join(p)

def utc_a_local(hora_utc_str, tz="Europe/Madrid"):
    try:
        hora_utc_str = hora_utc_str.replace("Z","")
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        hl = now_utc.replace(hour=int(hora_utc_str[:2]), minute=int(hora_utc_str[2:4]),
                             second=0, microsecond=0).astimezone(zoneinfo.ZoneInfo(tz))
        return hl.strftime("%H:%M (%Z)")
    except: return hora_utc_str + " UTC"

def enviar_telegram(msg, cfg):
    token = cfg.get("telegram_token",""); chat_id = cfg.get("telegram_chat_id","")
    if not token or not chat_id: log.warning("Telegram no configurado."); return
    try:
        r = requests.post("https://api.telegram.org/bot%s/sendMessage" % token,
                          json={"chat_id":chat_id,"text":msg,"parse_mode":"HTML"}, timeout=10)
        r.raise_for_status(); log.info("Alerta enviada por Telegram.")
    except requests.RequestException as e: log.error("Error Telegram: %s", e)

# ── Hilos monitor ─────────────────────────────────────────────────────────────
def hilo_recarga_log():
    while True:
        try:
            mins = float(leer_config().get("log_refresh_minutes", 1))
            mins = max(0.5, mins)
        except Exception:
            mins = 1
        time.sleep(mins * 60)
        log.info("Reloading log...")
        cargar_log()

def bucle_cluster():
    while True:
        if _cluster_paused.is_set():
            time.sleep(2); continue

        s = None; cfg = leer_config()
        if not cfg.get("cluster_host") or not cfg.get("cluster_login"):
            log.info("Cluster no configurado. Configure desde el dashboard.")
            _cluster_paused.set(); continue
        try:
            log.info("Conectando a %s:%d...", cfg["cluster_host"], cfg["cluster_port"])
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(20)
            s.connect((cfg["cluster_host"], int(cfg["cluster_port"])))
            buf = ""
            while "login:" not in buf.lower() and "call:" not in buf.lower():
                buf += s.recv(1024).decode("utf-8",errors="ignore")
            s.sendall((cfg["cluster_login"]+"\r\n").encode()); buf = ""
            while "password:" not in buf.lower():
                buf += s.recv(1024).decode("utf-8",errors="ignore")
            s.sendall((cfg["cluster_password"]+"\r\n").encode())
            log.info("Autenticado. Escuchando spots en tiempo real...")
            with _status_lock:
                _status["cluster_connected"] = True
                _status["cluster_host"] = "%s:%d" % (cfg["cluster_host"], cfg["cluster_port"])
            _escribir_status()
            time.sleep(1)
            for vcmd in [b"set/ve7cc\r\n", b"set/page 9999\r\n", b"unset/echo\r\n"]:
                s.sendall(vcmd); time.sleep(0.5)
            time.sleep(1); s.settimeout(2)
            try:
                while True:
                    lft = s.recv(4096).decode("utf-8",errors="ignore")
                    if not lft: break
            except socket.timeout: pass
            s.settimeout(5); s.sendall(b"sh/dx 20\r\n")
            log.info("Solicitados ultimos 20 spots.")
            buf = ""; uka = time.time()
            while True:
                if time.time()-uka > 180:
                    s.sendall(b"sh/dx 1\r\n"); uka = time.time(); log.info("Keepalive enviado.")
                try: chunk = s.recv(4096).decode("utf-8",errors="ignore")
                except socket.timeout: continue
                if not chunk:
                    log.warning("Conexion cerrada por el cluster.")
                    with _status_lock: _status["cluster_connected"] = False
                    _escribir_status(); break
                buf += chunk
                while "\n" in buf:
                    linea, buf = buf.split("\n",1); linea = linea.rstrip("\r")
                    if linea.strip(): procesar_linea(linea)
                if "disconnected" in buf.lower() or "reconnected" in buf.lower():
                    log.warning("Desconexion detectada."); break
        except Exception as e:
            log.warning("Error de conexion: %s", e)
            with _status_lock: _status["cluster_connected"] = False; _status["errores"] += 1
            _escribir_status()
        finally:
            if s:
                try: s.close()
                except: pass

        if _cluster_paused.is_set():
            log.info("Cluster desconectado. Esperando comando connect..."); continue

        log.info("Reconectando en 30s..."); time.sleep(30)

# ── Rutas Flask ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    with _status_lock: data = dict(_status)
    try:
        mtime = os.path.getmtime(STATUS_PATH)
        delta = datetime.datetime.now().timestamp() - mtime
        if delta < 120:    uptime_str = "hace %ds" % int(delta)
        elif delta < 3600: uptime_str = "hace %dm" % int(delta//60)
        else:              uptime_str = "hace %dh %dm" % (int(delta//3600), int((delta%3600)//60))
        data["status_age_sec"] = int(delta)
    except:
        uptime_str = "—"; data["status_age_sec"] = 9999
    data["status_last_update"] = uptime_str
    data["log_tail"]     = _leer_log_tail()
    data["monitor_alive"] = data.get("status_age_sec", 9999) < 300
    data["all_bands"]    = ALL_BANDS
    data["all_modes"]    = ALL_MODES
    return jsonify(data)

@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(leer_config())

@app.route("/api/config", methods=["POST"])
def api_config_update():
    try:
        new_data = request.get_json()
        current  = leer_config()
        if "cluster_port" in new_data: new_data["cluster_port"] = int(new_data["cluster_port"])
        if "qth_lat"      in new_data: new_data["qth_lat"]      = float(new_data["qth_lat"])
        if "qth_lon"      in new_data: new_data["qth_lon"]      = float(new_data["qth_lon"])
        if "locator" in new_data and new_data["locator"]:
            lat, lon = maidenhead_to_latlon(new_data["locator"])
            if lat is not None:
                new_data["qth_lat"] = lat; new_data["qth_lon"] = lon
        # Detectar si cambia log_type o log_path — disparar recarga inmediata
        reload_log = (
            ("log_type" in new_data and new_data["log_type"] != current.get("log_type")) or
            ("log_path" in new_data and new_data["log_path"] != current.get("log_path","") and new_data["log_path"]) or
            ("hrd_xml_dir" in new_data and new_data["hrd_xml_dir"] != current.get("hrd_xml_dir","") and new_data["hrd_xml_dir"])
        )
        current.update(new_data)
        _write_json(CONFIG_PATH, current)
        if reload_log:
            import threading
            _limpiar_stats_log()
            threading.Thread(target=cargar_log, daemon=True).start()
        return jsonify({"ok": True, "config": current})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/flags", methods=["GET"])
def api_flags_get():
    return jsonify(leer_flags())

@app.route("/api/flags", methods=["POST"])
def api_flags_update():
    try:
        new_flags = request.get_json()
        if "iaru_region"    in new_flags: new_flags["iaru_region"]    = int(new_flags["iaru_region"])
        if "bandas_activas" in new_flags: new_flags["bandas_activas"] = [b for b in new_flags["bandas_activas"] if b in ALL_BANDS]
        if "modos_activos"  in new_flags: new_flags["modos_activos"]  = [m for m in new_flags["modos_activos"]  if m in ALL_MODES]
        current = leer_flags(); current.update(new_flags)
        _write_json(FLAGS_PATH, current)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/cluster/connect", methods=["POST"])
def api_cluster_connect():
    cfg = leer_config()
    if not cfg.get("cluster_host") or not cfg.get("cluster_login"):
        return jsonify({"ok": False, "error": "Host o login no configurados"}), 400
    log.info("Conexion solicitada desde dashboard.")
    _cluster_paused.clear()
    return jsonify({"ok": True})

@app.route("/api/cluster/disconnect", methods=["POST"])
def api_cluster_disconnect():
    log.info("Desconexion solicitada desde dashboard.")
    _cluster_paused.set()
    with _status_lock: _status["cluster_connected"] = False
    _escribir_status()
    return jsonify({"ok": True})

@app.route("/api/browse")
def api_browse():
    path   = request.args.get("path", "/hostfs").strip() or "/hostfs"
    exts_q = request.args.get("exts", "").strip()
    exts   = [e.strip().lower() for e in exts_q.split(",") if e.strip()] if exts_q else []
    path   = os.path.normpath(path)
    if not path.startswith("/hostfs"): path = "/hostfs"
    try:
        if not os.path.isdir(path): path = os.path.dirname(path) or "/hostfs"
        entries = os.listdir(path)
        dirs    = sorted([e for e in entries
                          if os.path.isdir(os.path.join(path, e)) and not e.startswith(".")],
                         key=lambda x: x.lower())
        files   = []
        if exts:
            files = sorted([e for e in entries
                            if os.path.isfile(os.path.join(path, e))
                            and any(e.lower().endswith(x) for x in exts)],
                           key=lambda x: x.lower())
        parent = os.path.dirname(path) if path != "/hostfs" else None
        host_path_display = path[len("/hostfs"):] or "/"
        return jsonify({"ok": True, "path": path, "host_path": host_path_display,
                        "dirs": dirs, "files": files, "parent": parent})
    except PermissionError:
        parent = os.path.dirname(path) if path != "/hostfs" else None
        return jsonify({"ok": False, "path": path, "host_path": path[len("/hostfs"):] or "/",
                        "dirs": [], "files": [], "parent": parent, "error": "Sin permiso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "path": path,
                        "host_path": "/", "dirs": [], "files": [], "parent": None})

@app.route("/api/alerts/stream")
def api_alerts_stream():
    q = queue.Queue(maxsize=20)
    with _sse_lock: _sse_clients.append(q)
    def generate():
        # Enviar alertas actuales al conectar
        with _status_lock: current = list(_status.get("last_alerts",[]))
        yield f"data: {json.dumps(current, ensure_ascii=False)}\n\n"
        while True:
            try:
                data = q.get(timeout=25)
                yield f"data: {data}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"}
    )

@app.route("/api/log/reload", methods=["POST"])
def api_log_reload():
    """Fuerza recarga inmediata del log — llamado tras cambiar tipo o path."""
    import threading
    _limpiar_stats_log()
    threading.Thread(target=cargar_log, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/telegram/test", methods=["POST"])
def api_telegram_test():
    cfg     = leer_config()
    token   = cfg.get("telegram_token","")
    chat_id = cfg.get("telegram_chat_id","")
    body    = request.get_json(silent=True) or {}
    ui_lang = body.get("lang","es")
    if not token or not chat_id:
        return jsonify({"ok": False, "error": "Token o Chat ID no configurados"}), 400
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if ui_lang == "en":
        msg = f"🧪 <b>Test DX Monitor</b>\n━━━━━━━━━━━━━━━━━━━━\n✅ Telegram connection OK\n🕐 {now}\n📡 Dashboard working correctly"
    else:
        msg = f"🧪 <b>Test DX Monitor</b>\n━━━━━━━━━━━━━━━━━━━━\n✅ Conexión Telegram operativa\n🕐 {now}\n📡 Dashboard funcionando correctamente"
    try:
        r    = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        data = r.json()
        if data.get("ok"): return jsonify({"ok": True, "message_id": data["result"]["message_id"]})
        return jsonify({"ok": False, "error": data.get("description","Error Telegram")}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global _pfx_cty
    inicializar_config(); inicializar_flags(); cfg = leer_config()
    log.info("=== DX Monitor Docker %s ===", VERSION)
    log.info("Indicativo: %s  Locator: %s", cfg.get("callsign","?"), cfg.get("locator","?"))
    actualizar_bigcty(CTY_PATH); _pfx_cty = cargar_cty_dat(CTY_PATH); cargar_log()

    # Hilos del monitor
    threading.Thread(target=hilo_recarga_log,    daemon=True).start()
    threading.Thread(target=hilo_actualizar_cty, daemon=True).start()

    # Autoconectar si hay config guardada, si no esperar
    if not cfg.get("cluster_host") or not cfg.get("cluster_login"):
        log.info("Cluster no configurado. Configure desde el dashboard y pulse Conectar.")
        _cluster_paused.set()

    # Bucle cluster en hilo daemon
    threading.Thread(target=bucle_cluster, daemon=True).start()

    # Flask en el hilo principal
    log.info("Dashboard en http://0.0.0.0:8765")
    app.run(host="0.0.0.0", port=8765, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
