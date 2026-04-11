#!/usr/bin/env python3
"""DX Monitor Docker — v13 — proceso único (monitor + web)"""

import xml.etree.ElementTree as ET
import socket, time, logging, glob, os, re, datetime, zoneinfo, json, threading, math, queue
from collections import defaultdict
import requests
from flask import Flask, jsonify, render_template, request, Response, stream_with_context
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
    "hrd_xml_dir":"","hrd_xml_glob":"*.xml",
    "cluster_host":"","cluster_port":7300,
    "cluster_login":"","cluster_password":"",
    "telegram_token":"","telegram_chat_id":"",
    "timezone":"Europe/Madrid","alert_lang":"es","time_mode":"local",
}

FLAGS_DEFAULT = {
    "pais_nuevo":True,"pais_trabajado":True,"banda_nueva":True,"banda_sin_qsl":False,
    "modo_nuevo":True,"modo_sin_qsl":False,
    "bandas_activas":ALL_BANDS[:],"modos_activos":ALL_MODES[:],"iaru_region":1,
}

# ── Traducciones de log ───────────────────────────────────────────────────────
_LOG_STRINGS = {
    "cfg_created":        {"es": "config.json creado con valores por defecto.",
                           "en": "config.json created with default values."},
    "cfg_migrated":       {"es": "config.json migrado.",
                           "en": "config.json migrated."},
    "cfg_read_error":     {"es": "Error leyendo config.json: %s",
                           "en": "Error reading config.json: %s"},
    "cfg_migrate_error":  {"es": "Error migrando config.json: %s",
                           "en": "Error migrating config.json: %s"},
    "flags_created":      {"es": "flags.json creado.",
                           "en": "flags.json created."},
    "flags_migrated":     {"es": "flags.json migrado.",
                           "en": "flags.json migrated."},
    "status_write_error": {"es": "Error escribiendo status.json: %s",
                           "en": "Error writing status.json: %s"},
    "cty_no_new":         {"es": "Big CTY actualizado. No hay nueva version.",
                           "en": "Big CTY up to date. No new version."},
    "cty_downloading":    {"es": "Descargando nueva version de Big CTY...",
                           "en": "Downloading new Big CTY version..."},
    "cty_bad":            {"es": "Big CTY incorrecto (%d lineas).",
                           "en": "Big CTY invalid (%d lines)."},
    "cty_updated":        {"es": "Big CTY actualizado: %d lineas.",
                           "en": "Big CTY updated: %d lines."},
    "cty_update_error":   {"es": "Error al actualizar Big CTY: %s",
                           "en": "Error updating Big CTY: %s"},
    "cty_not_found":      {"es": "No se encontro cty.dat en %s",
                           "en": "cty.dat not found at %s"},
    "cty_loaded":         {"es": "cty.dat cargado: %d prefijos.",
                           "en": "cty.dat loaded: %d prefixes."},
    "xml_error":          {"es": "Error XML: %s",
                           "en": "XML error: %s"},
    "pfx_built":          {"es": "Tabla prefijo->DXCC construida: %d prefijos.",
                           "en": "Prefix->DXCC table built: %d prefixes."},
    "xml_not_found":      {"es": "No se encontro ningun XML en %s",
                           "en": "No XML found in %s"},
    "xml_parse_error":    {"es": "Error al parsear XML: %s",
                           "en": "XML parse error: %s"},
    "xml_records":        {"es": "XML: %s — %d registros",
                           "en": "XML: %s — %d records"},
    "log_loaded":         {"es": "Log cargado: %d DXCC confirmados, %d trabajados. Sin DXCC: %d",
                           "en": "Log loaded: %d DXCC confirmed, %d worked. No DXCC: %d"},
    "spot_no_dxcc":       {"es": "SPOT sin DXCC: %s %.3f %s/%s",
                           "en": "SPOT no DXCC: %s %.3f %s/%s"},
    "spot_info":          {"es": "SPOT %s [%d] %s %s/%s -> %s",
                           "en": "SPOT %s [%d] %s %s/%s -> %s"},
    "alert_sent_log":     {"es": "ALERTA %s: %s [%d] %s %s/%s",
                           "en": "ALERT %s: %s [%d] %s %s/%s"},
    "tg_not_configured":  {"es": "Telegram no configurado.",
                           "en": "Telegram not configured."},
    "tg_sent":            {"es": "Alerta enviada por Telegram.",
                           "en": "Alert sent via Telegram."},
    "tg_error":           {"es": "Error Telegram: %s",
                           "en": "Telegram error: %s"},
    "log_reloading":      {"es": "Recargando log HRD...",
                           "en": "Reloading HRD log..."},
    "cluster_not_cfg":    {"es": "Cluster no configurado. Configure desde el dashboard.",
                           "en": "Cluster not configured. Configure from the dashboard."},
    "cluster_connecting": {"es": "Conectando a %s:%d...",
                           "en": "Connecting to %s:%d..."},
    "cluster_auth":       {"es": "Autenticado. Escuchando spots en tiempo real...",
                           "en": "Authenticated. Listening for real-time spots..."},
    "cluster_hist":       {"es": "Solicitados ultimos 20 spots.",
                           "en": "Requested last 20 spots."},
    "cluster_hist_done":  {"es": "Spots historicos registrados. Escuchando stream en tiempo real...",
                           "en": "Historical spots registered. Listening to real-time stream..."},
    "cluster_keepalive":  {"es": "Keepalive enviado.",
                           "en": "Keepalive sent."},
    "cluster_closed":     {"es": "Conexion cerrada por el cluster.",
                           "en": "Connection closed by cluster."},
    "cluster_disconn":    {"es": "Desconexion detectada.",
                           "en": "Disconnection detected."},
    "cluster_conn_error": {"es": "Error de conexion: %s",
                           "en": "Connection error: %s"},
    "cluster_waiting":    {"es": "Cluster desconectado. Esperando comando connect...",
                           "en": "Cluster disconnected. Waiting for connect command..."},
    "cluster_reconnect":  {"es": "Reconectando en 30s...",
                           "en": "Reconnecting in 30s..."},
    "cluster_req_connect":{"es": "Conexion solicitada desde dashboard.",
                           "en": "Connection requested from dashboard."},
    "cluster_req_disconn":{"es": "Desconexion solicitada desde dashboard.",
                           "en": "Disconnection requested from dashboard."},
    "startup_call":       {"es": "Indicativo: %s  Locator: %s",
                           "en": "Callsign: %s  Locator: %s"},
    "cluster_not_cfg2":   {"es": "Cluster no configurado. Configure desde el dashboard y pulse Conectar.",
                           "en": "Cluster not configured. Configure from dashboard and press Connect."},
    "dashboard_url":      {"es": "Dashboard en http://0.0.0.0:8765",
                           "en": "Dashboard at http://0.0.0.0:8765"},
}

def _t(key):
    """Devuelve el string de log en el idioma configurado en config.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            lang = json.load(f).get("alert_lang", "es")
    except Exception:
        lang = "es"
    entry = _LOG_STRINGS.get(key, {})
    return entry.get(lang, entry.get("es", key))

# ── Logging ───────────────────────────────────────────────────────────────────
import logging.handlers

class LocalTimezoneFormatter(logging.Formatter):
    """Formatter que usa la timezone configurada en config.json."""
    def formatTime(self, record, datefmt=None):
        try:
            import json, zoneinfo
            with open(CONFIG_PATH,"r",encoding="utf-8") as f: cfg = json.load(f)
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
    "callsign":"","locator":"",
}
_status_lock = threading.Lock()
_cluster_paused = threading.Event()

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
    with open(tmp,"w",encoding="utf-8") as f: json.dump(data, f, indent=2)
    os.replace(tmp, path)

def leer_config():
    cfg = dict(CONFIG_DEFAULTS)
    try:
        with open(CONFIG_PATH,"r",encoding="utf-8") as f: datos = json.load(f)
        cfg.update(datos)
    except FileNotFoundError: pass
    except Exception as e: log.warning(_t("cfg_read_error"), e)
    if cfg.get("locator") and cfg["qth_lat"] == 0.0 and cfg["qth_lon"] == 0.0:
        lat, lon = maidenhead_to_latlon(cfg["locator"])
        if lat: cfg["qth_lat"] = lat; cfg["qth_lon"] = lon
    return cfg

def inicializar_config():
    if not os.path.exists(CONFIG_PATH):
        _write_json(CONFIG_PATH, CONFIG_DEFAULTS)
        log.info(_t("cfg_created"))
    else:
        try:
            with open(CONFIG_PATH,"r",encoding="utf-8") as f: datos = json.load(f)
            updated = False
            for k, v in CONFIG_DEFAULTS.items():
                if k not in datos: datos[k] = v; updated = True
            if updated:
                _write_json(CONFIG_PATH, datos)
                log.info(_t("cfg_migrated"))
        except Exception as e: log.warning(_t("cfg_migrate_error"), e)

def leer_flags():
    try:
        with open(FLAGS_PATH,"r",encoding="utf-8") as f: datos = json.load(f)
        flags = dict(FLAGS_DEFAULT); flags.update(datos); return flags
    except: return dict(FLAGS_DEFAULT)

def inicializar_flags():
    if not os.path.exists(FLAGS_PATH):
        _write_json(FLAGS_PATH, FLAGS_DEFAULT)
        log.info(_t("flags_created"))
    else:
        try:
            with open(FLAGS_PATH,"r",encoding="utf-8") as f: datos = json.load(f)
            updated = False
            for k, v in FLAGS_DEFAULT.items():
                if k not in datos: datos[k] = v; updated = True
            if updated:
                _write_json(FLAGS_PATH, datos)
                log.info(_t("flags_migrated"))
        except: pass

def _escribir_status():
    tmp = STATUS_PATH + ".tmp"
    try:
        with _status_lock: data = dict(_status)
        with open(tmp,"w",encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, default=str)
        os.replace(tmp, STATUS_PATH)
        sse_push(json.dumps(data.get("last_alerts",[]), ensure_ascii=False))
    except Exception as e: log.warning(_t("status_write_error"), e)

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
                log.info(_t("cty_no_new")); return False
        log.info(_t("cty_downloading"))
        tmp = path+".tmp"; urllib.request.urlretrieve(url, tmp)
        with open(tmp,'r',encoding="utf-8",errors='ignore') as f: lineas = f.readlines()
        if len(lineas) < 1000:
            log.error(_t("cty_bad"), len(lineas)); os.remove(tmp); return False
        os.replace(tmp, path); log.info(_t("cty_updated"), len(lineas)); return True
    except Exception as e: log.warning(_t("cty_update_error"), e); return False

def hilo_actualizar_cty():
    while True:
        time.sleep(86400)
        if actualizar_bigcty(CTY_PATH):
            global _pfx_cty, _pfx_a_dxcc
            _pfx_cty = cargar_cty_dat(CTY_PATH)
            cfg = leer_config()
            ficheros = glob.glob(os.path.join(host_path(cfg["hrd_xml_dir"]), cfg["hrd_xml_glob"]))
            if ficheros: _pfx_a_dxcc = construir_pfx_a_dxcc(max(ficheros, key=os.path.getmtime))

def cargar_cty_dat(path):
    pfx_cty = {}
    try:
        with open(path,"r",encoding="utf-8",errors="ignore") as f: contenido = f.read()
    except FileNotFoundError: log.error(_t("cty_not_found"), path); return pfx_cty
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
    log.info(_t("cty_loaded"), len(pfx_cty)); return pfx_cty

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
    except Exception as e: log.error(_t("xml_error"), e); return {}
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
    log.info(_t("pfx_built"), len(pfx_map)); return pfx_map

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
    global _confirmados, _trabajados, _pfx_a_dxcc
    cfg = leer_config()
    ficheros = glob.glob(os.path.join(host_path(cfg["hrd_xml_dir"]), cfg["hrd_xml_glob"]))
    if not ficheros:
        log.error(_t("xml_not_found"), os.path.join(host_path(cfg["hrd_xml_dir"]), cfg["hrd_xml_glob"])); return
    path = max(ficheros, key=os.path.getmtime)
    _pfx_a_dxcc = construir_pfx_a_dxcc(path)
    try: tree = ET.parse(path); root = tree.getroot()
    except ET.ParseError as e: log.error(_t("xml_parse_error"), e); return
    cn = defaultdict(lambda: defaultdict(set)); tn = defaultdict(lambda: defaultdict(set))
    registros = root.findall("LogbookBackup/Record")
    log.info(_t("xml_records"), os.path.basename(path), len(registros))
    sin = 0
    for rec in registros:
        a = rec.attrib; dxcc = a.get("COL_DXCC","").strip(); banda = a.get("COL_BAND","").strip().lower()
        modo = normalizar_modo(a.get("COL_MODE",""))
        qsl = (a.get("COL_QSL_RCVD","").upper()=="Y" or a.get("COL_LOTW_QSL_RCVD","").upper() in ("Y","V"))
        if not dxcc or not banda or not modo: sin += 1; continue
        try: dn = int(dxcc)
        except: sin += 1; continue
        tn[dn][banda].add(modo)
        if qsl: cn[dn][banda].add(modo)
    with _lock: _confirmados = cn; _trabajados = tn
    log.info(_t("log_loaded"), len(cn), len(tn), sin)
    cty_mtime = ""
    try: cty_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(CTY_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    except: pass
    with _status_lock:
        _status["dxcc_confirmados"] = len(cn); _status["dxcc_trabajados"] = len(tn)
        _status["qsos_total"]  = len(registros); _status["pfx_tabla"]  = len(_pfx_a_dxcc)
        _status["pfx_cty"]     = len(_pfx_cty);  _status["xml_hrd_path"] = os.path.basename(path)
        _status["cty_dat_mtime"] = cty_mtime
        cfg2 = leer_config()
        _status["callsign"] = cfg2.get("callsign",""); _status["locator"] = cfg2.get("locator","")
    _escribir_status()

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

def procesar_linea(linea, solo_registrar=False):
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
        # Rango asimétrico: -1 kHz / +3 kHz sobre la frecuencia base
        ft4_match = any(-1 <= freq_khz - f <= 3 for f in FT4_FREQS.values())
        ft8_match = any(-1 <= freq_khz - f <= 3 for f in FT8_FREQS.values())
        if ft4_match:
            modo = "FT4"
        elif ft8_match:
            modo = "FT8"
        else:
            inferido = infer_mode_by_freq(freq_khz, region) or "SSB"
            if inferido in ["RTTY","FT8","FT4"]:
                inferido = "SSB" if banda_permite_ssb(freq_khz, region) else "CW"
            modo = inferido

    if is_cw_segment(freq_khz, region) and modo not in ["SSB","RTTY","FT8","FT4"]:
        modo = "CW"
    if modo not in modos_activos: return

    dxcc_num, nombre, dx_lat, dx_lon = call_a_dxcc(call)
    if not dxcc_num:
        log.info(_t("spot_no_dxcc"), call, freq, banda, modo); return

    ahora = time.time()
    with _lock_alertas:
        _alertas_enviadas = {(c,b,mo,t) for c,b,mo,t in _alertas_enviadas if ahora-t < 600}
        if any(c==call and b==banda and mo==modo for c,b,mo,t in _alertas_enviadas): return

    # Spots históricos: registrar en antiduplicado pero no alertar
    if solo_registrar:
        with _lock_alertas: _alertas_enviadas.add((call, banda, modo, ahora))
        return

    tipo, icono = clasificar_spot(dxcc_num, banda, modo, flags)
    log.info(_t("spot_info"), call, dxcc_num, nombre, banda, modo, tipo or "ALREADY_CONFIRMED")
    if not tipo: return

    with _lock_alertas: _alertas_enviadas.add((call, banda, modo, ahora))
    log.info(_t("alert_sent_log"), tipo, call, dxcc_num, nombre, banda, modo)

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

    # Hora para la tabla de últimas alertas — respeta time_mode y timezone
    if time_mode == "utc":
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    else:
        try:
            tz_cfg = zoneinfo.ZoneInfo(cfg.get("timezone","Europe/Madrid"))
            now_str = datetime.datetime.now(tz_cfg).strftime("%H:%M:%S")
        except Exception:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

    entry = {"ts":now_str,"call":call,"dxcc":nombre,"freq":"%.3f"%freq,
             "banda":banda,"modo":modo,"tipo":tipo,"icono":icono,
             "time_mode":time_mode}
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
    if not token or not chat_id: log.warning(_t("tg_not_configured")); return
    try:
        r = requests.post("https://api.telegram.org/bot%s/sendMessage" % token,
                          json={"chat_id":chat_id,"text":msg,"parse_mode":"HTML"}, timeout=10)
        r.raise_for_status(); log.info(_t("tg_sent"))
    except requests.RequestException as e: log.error(_t("tg_error"), e)

# ── Hilos monitor ─────────────────────────────────────────────────────────────
def hilo_recarga_log():
    while True:
        time.sleep(60); log.info(_t("log_reloading")); cargar_log_hrd()

def bucle_cluster():
    while True:
        if _cluster_paused.is_set():
            time.sleep(2); continue

        s = None; cfg = leer_config()
        if not cfg.get("cluster_host") or not cfg.get("cluster_login"):
            log.info(_t("cluster_not_cfg"))
            _cluster_paused.set(); continue
        try:
            log.info(_t("cluster_connecting"), cfg["cluster_host"], cfg["cluster_port"])
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(20)
            s.connect((cfg["cluster_host"], int(cfg["cluster_port"])))
            buf = ""
            while "login:" not in buf.lower() and "call:" not in buf.lower():
                buf += s.recv(1024).decode("utf-8",errors="ignore")
            s.sendall((cfg["cluster_login"]+"\r\n").encode()); buf = ""
            while "password:" not in buf.lower():
                buf += s.recv(1024).decode("utf-8",errors="ignore")
            s.sendall((cfg["cluster_password"]+"\r\n").encode())
            log.info(_t("cluster_auth"))
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
            log.info(_t("cluster_hist"))
            # Recoger respuesta del sh/dx 20 por separado y registrar sin alertar
            hist_buf = ""; t_last = time.time()
            while time.time() - t_last < 3.0:
                try:
                    chunk = s.recv(4096).decode("utf-8", errors="ignore")
                    if chunk: hist_buf += chunk; t_last = time.time()
                except socket.timeout: pass
            for linea in hist_buf.splitlines():
                if linea.strip(): procesar_linea(linea, solo_registrar=True)
            log.info(_t("cluster_hist_done"))
            buf = ""; uka = time.time()
            while True:
                if time.time()-uka > 180:
                    s.sendall(b"sh/dx 1\r\n"); uka = time.time(); log.info(_t("cluster_keepalive"))
                try: chunk = s.recv(4096).decode("utf-8",errors="ignore")
                except socket.timeout: continue
                if not chunk:
                    log.warning(_t("cluster_closed"))
                    with _status_lock: _status["cluster_connected"] = False
                    _escribir_status(); break
                buf += chunk
                while "\n" in buf:
                    linea, buf = buf.split("\n",1); linea = linea.rstrip("\r")
                    if linea.strip(): procesar_linea(linea)
                if "disconnected" in buf.lower() or "reconnected" in buf.lower():
                    log.warning(_t("cluster_disconn")); break
        except Exception as e:
            log.warning(_t("cluster_conn_error"), e)
            with _status_lock: _status["cluster_connected"] = False; _status["errores"] += 1
            _escribir_status()
        finally:
            if s:
                try: s.close()
                except: pass

        if _cluster_paused.is_set():
            log.info(_t("cluster_waiting")); continue

        log.info(_t("cluster_reconnect")); time.sleep(30)

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
        data["status_age_sec"] = int(delta)
    except:
        data["status_age_sec"] = 9999
    data["log_tail"]      = _leer_log_tail()
    data["monitor_alive"] = data.get("status_age_sec", 9999) < 300
    data["all_bands"]     = ALL_BANDS
    data["all_modes"]     = ALL_MODES
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
        current.update(new_data)
        _write_json(CONFIG_PATH, current)
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
    log.info(_t("cluster_req_connect"))
    _cluster_paused.clear()
    return jsonify({"ok": True})

@app.route("/api/cluster/disconnect", methods=["POST"])
def api_cluster_disconnect():
    log.info(_t("cluster_req_disconn"))
    _cluster_paused.set()
    with _status_lock: _status["cluster_connected"] = False
    _escribir_status()
    return jsonify({"ok": True})

@app.route("/api/browse")
def api_browse():
    path = request.args.get("path", "/hostfs").strip() or "/hostfs"
    path = os.path.normpath(path)
    if not path.startswith("/hostfs"): path = "/hostfs"
    try:
        if not os.path.isdir(path): path = os.path.dirname(path) or "/hostfs"
        entries  = os.listdir(path)
        dirs     = sorted([e for e in entries
                           if os.path.isdir(os.path.join(path, e)) and not e.startswith(".")])
        parent   = os.path.dirname(path) if path != "/hostfs" else None
        host_path_display = path[len("/hostfs"):] or "/"
        return jsonify({"ok": True, "path": path, "host_path": host_path_display,
                        "dirs": dirs, "parent": parent})
    except PermissionError:
        parent = os.path.dirname(path) if path != "/hostfs" else None
        return jsonify({"ok": False, "path": path, "host_path": path[len("/hostfs"):] or "/",
                        "dirs": [], "parent": parent, "error": "Sin permiso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "path": path,
                        "host_path": "/", "dirs": [], "parent": None})

@app.route("/api/alerts/stream")
def api_alerts_stream():
    q = queue.Queue(maxsize=20)
    with _sse_lock: _sse_clients.append(q)
    def generate():
        with _status_lock: current = list(_status.get("last_alerts",[]))
        yield f"data: {json.dumps(current, ensure_ascii=False)}\n\n"
        try:
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                try: _sse_clients.remove(q)
                except ValueError: pass
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"}
    )

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
    log.info(_t("startup_call"), cfg.get("callsign","?"), cfg.get("locator","?"))
    actualizar_bigcty(CTY_PATH); _pfx_cty = cargar_cty_dat(CTY_PATH); cargar_log_hrd()

    threading.Thread(target=hilo_recarga_log,    daemon=True).start()
    threading.Thread(target=hilo_actualizar_cty, daemon=True).start()

    if not cfg.get("cluster_host") or not cfg.get("cluster_login"):
        log.info(_t("cluster_not_cfg2"))
        _cluster_paused.set()

    threading.Thread(target=bucle_cluster, daemon=True).start()

    log.info(_t("dashboard_url"))
    app.run(host="0.0.0.0", port=8765, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
