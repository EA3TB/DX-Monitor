# DX Monitor — Windows

Standalone DX Cluster monitor for Windows. No installation required — single `.exe` file.

**Version**: v1.3 | [Download latest release](https://github.com/EA3TB/DX-Monitor/releases/latest)

---

## Requirements

- Windows 10/11 (64-bit)
- No installation needed
- For **Swisslog MDB** support: Microsoft Access Database Engine 2016 (the app will offer to install it automatically if missing)

---

## Quick start

1. Download `DXMonitor.exe` from [Releases](https://github.com/EA3TB/DX-Monitor/releases/latest)
2. Run `DXMonitor.exe` — a system tray icon appears
3. Open `http://127.0.0.1:8765` in your browser
4. Configure your callsign, log source, cluster and Telegram bot from the dashboard
5. Click **Connect**

The app runs minimized in the system tray. Right-click the tray icon to open the dashboard or exit.

---

## Features

- Real-time DX Cluster monitoring (CC11/VE7CC protocol)
- Telegram alerts for new DXCC, new band, new mode, unconfirmed QSLs
- Web dashboard with dark/light theme and ES/EN language
- Alert filters: IARU region, bands, modes, alert types
- Mode inference from frequency (FT8, FT4, CW, SSB)
- Big CTY database auto-update (daily, from country-files.com)
- **Multi log source support**:
  - HRD XML (Ham Radio Deluxe — automatic background export)
  - Swisslog MDB (Microsoft Access database)
  - Log4OM SQLite (version 2)
  - ADIF (any logging software)
- Configurable log refresh interval
- SSE real-time alerts in dashboard (no polling)
- Bilingual alert messages (ES/EN), local/UTC time
- **HF propagation scoring** — real-time SP/LP scores per spot, using current SFI and Kp
- **Propagation minimum filter** — discard spots below a configured score threshold

---

## Configuration

All configuration is managed from the dashboard at `http://127.0.0.1:8765`. Settings are saved to `config.json` in the application data directory.

| Field | Description |
|---|---|
| Callsign | Your amateur radio callsign |
| Locator | Maidenhead locator — auto-calculates lat/lon |
| Log type | HRD XML / Swisslog MDB / Log4OM SQLite / ADIF |
| Log file/directory | Path to your log file or XML directory |
| Refresh interval | Log reload interval in minutes |
| Cluster host | DX Cluster hostname |
| Cluster port | TCP port (default 7300) |
| Cluster login | Login callsign |
| Cluster password | Password (hideable with 👁 button) |
| Telegram token | Bot token (hideable with 👁 button) |
| Telegram chat ID | Your chat ID |
| Alert language | Spanish / English |
| Timezone | 40+ zones grouped by region + manual IANA field |
| Time mode | Local (per timezone) / UTC |

---

## Alert filters

Configurable from the dashboard, saved to `flags.json`:

- **IARU region**: R1 (Europe/Africa), R2 (Americas), R3 (Asia-Pacific)
- **Active bands**: individual selection or all/none
- **Active modes**: CW, SSB, RTTY, FT8, FT4
- **Alert types**:
  - New country — DXCC never worked
  - Worked country — worked but no QSL
  - New band — DXCC not worked on this band
  - Band without QSL — band worked, QSL pending
  - New mode — DXCC/band not worked in this mode
  - Mode without QSL — mode worked, QSL pending
- **Propagation minimum** (`prop_min`) — discard spots where `max(SP, LP) < prop_min`. Set to 0 to disable.

---

## HF Propagation scoring

Each alert includes a real-time propagation score for the spot path (QTH → DX) on the spot's exact frequency:

- **SP** — Short Path score (0–99)
- **LP** — Long Path score (0–99)

Scores are calculated using:

- **SFI** (Solar Flux Index) — fetched from [HamQSL](https://www.hamqsl.com/solarxml.php) every 15 minutes
- **Kp** (geomagnetic index) — fetched from [NOAA SWPC](https://services.swpc.noaa.gov/json/planetary_k_index_1m.json) every 15 minutes
- Path distance, midpoint latitude, solar hour at midpoint, and spot frequency relative to estimated MUF

Scores appear in Telegram alerts. The `prop_min` filter in Alert Filters allows discarding spots with poor propagation.

---

## Data files

The app stores its data in the same directory as the `.exe` (or the working directory if run from source):

| File | Description |
|---|---|
| `config.json` | All user configuration |
| `flags.json` | Alert filters and active bands/modes |
| `status.json` | Runtime status (cluster, log stats, last alerts) |
| `dx_monitor.log` | Application log (weekly rotation, 4 weeks kept) |
| `cty.dat` | Big CTY prefix database (auto-updated daily) |

---

## Build from source

```powershell
cd windows
pip install flask requests pyinstaller tzdata pystray Pillow comtypes
python generar_ico.py
pyinstaller dx_monitor.spec --clean
```

The compiled `DXMonitor.exe` will be in `dist/`.

### Source files

| File | Description |
|---|---|
| `main_windows.py` | Main process (monitor + Flask web server + tray icon) |
| `hf_propagation.py` | HF propagation scoring engine (no external deps) |
| `log_readers.py` | Log readers: HRD XML, Swisslog MDB, Log4OM SQLite, ADIF |
| `band_plans.py` | IARU R1/R2/R3 band plans, mode inference |
| `dx_monitor.spec` | PyInstaller build spec |
| `generar_ico.py` | Generates `dx_monitor.ico` for the tray icon |
| `compilar.bat` | Build helper script |
| `requirements_windows.txt` | Python dependencies |
| `templates/dashboard.html` | Web dashboard |

---

## Troubleshooting

**App does not start / port in use**
Check that port 8765 is not used by another process:
```
netstat -ano | findstr :8765
```

**Swisslog MDB: Access Database Engine error**
Install [Microsoft Access Database Engine 2016 (64-bit)](https://www.microsoft.com/en-us/download/details.aspx?id=54920). The app will detect the missing driver and offer a download link automatically.

**Cluster connects but no spots appear**
- Verify the cluster supports CC11/VE7CC protocol (`set/ve7cc` command)
- Check that the configured bands and modes in Alert Filters are active
- Check the log panel in the dashboard for connection messages

**Propagation always shows "Fail"**
The app could not fetch SFI or Kp from the internet. Check network connectivity. The app will retry every 15 minutes. Alerts are still sent normally — propagation data is informational only.

---

73 de EA3TB
