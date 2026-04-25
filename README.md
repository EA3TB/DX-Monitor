# DX Monitor

DX Cluster monitor with Telegram alerts and web dashboard. Available for **Windows** (standalone `.exe`) and **Docker** (NAS/Linux).

**Callsign**: EA3TB | **Version**: v1.1 | **Docker Hub**: `ea3tb/dx-monitor:latest`

![DX Monitor Dashboard](https://raw.githubusercontent.com/EA3TB/DX-Monitor/main/screenshots/dashboard.png)

---

![DX Monitor Alerts](https://raw.githubusercontent.com/EA3TB/DX-Monitor/main/screenshots/alerts.png)

---

## Documentation

| | English | Español |
|---|---|---|
| ✈️ Telegram setup | [Guide](https://ea3tb.github.io/DX-Monitor/dx_monitor_telegram_ENG.html) | [Guía](https://ea3tb.github.io/DX-Monitor/dx_monitor_telegram_SPA.html) |
| 🍓 Raspberry Pi install | [Guide](https://ea3tb.github.io/DX-Monitor/dx_monitor_raspberry_ENG.html) | [Guía](https://ea3tb.github.io/DX-Monitor/dx_monitor_raspberry_SPA.html) |

---

## Features

- Real-time DX Cluster monitoring (CC11/VE7CC protocol)
- Telegram alerts for new DXCC, new band, new mode, unconfirmed QSLs
- Web dashboard with dark/light theme and ES/EN language
- Alert filters: IARU region, bands, modes, alert types
- Mode inference from frequency (FT8, FT4, CW, SSB)
- Big CTY database auto-update
- **Multi log source support**:
  - HRD XML (Ham Radio Deluxe — automatic background export)
  - Swisslog MDB (Microsoft Access database)
  - Log4OM SQLite (version 2)
  - ADIF (any logging software)
- Configurable log refresh interval
- SSE real-time alerts in dashboard (no polling)
- Bilingual alert messages (ES/EN), local/UTC time

---

## Windows

### Download

Download `DXMonitor.exe` from [Releases](https://github.com/EA3TB/DX-Monitor/releases/latest) — no installation required, just run it.

### Requirements

- Windows 10/11 (64-bit)
- No installation needed
- For **Swisslog MDB** support: Microsoft Access Database Engine 2016 (the app will offer to install it automatically if missing)

### Usage

1. Run `DXMonitor.exe`
2. Open `http://127.0.0.1:8765` in your browser
3. Configure your callsign, log source, cluster and Telegram bot
4. Click **Connect**

### Build from source

```powershell
cd windows
pip install flask requests pyinstaller tzdata pystray Pillow comtypes
python generar_ico.py
pyinstaller dx_monitor.spec --clean
```

---

## Docker

### Quick start

Create a `docker-compose.yml` file:

```yaml
services:
  dxmonitor:
    image: ea3tb/dx-monitor:latest
    container_name: dx_monitor_docker
    restart: unless-stopped
    ports:
      - "8765:8765"
    volumes:
      - /:/hostfs:ro
      - dx_docker_data:/opt/dx_monitor_docker
      # Optional: mount a shared folder from your local PC (SMB/CIFS)
      # Uncomment and adjust if you want to access MDB/SQLite/ADIF log files from your PC
      # - pc_logs:/hostfs/mnt/pc_logs:ro
    networks:
      - dx_net

volumes:
  dx_docker_data:
    driver: local
  # Optional: SMB volume to access log files from a local PC
  # Uncomment and adjust the IP address, share name and credentials
  # pc_logs:
  #   driver: local
  #   driver_opts:
  #     type: cifs
  #     device: "//192.168.X.X/ShareName"
  #     o: "guest,uid=1000,gid=1000,iocharset=utf8,vers=2.0"
  #     # If the share requires a username and password, replace guest with:
  #     # o: "username=USER,password=PASSWORD,uid=1000,gid=1000,iocharset=utf8,vers=2.0"

networks:
  dx_net:
    driver: bridge
```

Then:

```bash
docker compose up -d
```

Open `http://<nas-ip>:8765` in your browser and configure from the dashboard.

### Useful commands

```bash
# Real-time logs
docker logs -f dx_monitor_docker

# Status
docker compose ps

# Stop / start
docker compose down
docker compose up -d

# Access container shell
docker exec -it dx_monitor_docker bash

# View active config
docker exec dx_monitor_docker cat /opt/dx_monitor_docker/config.json
```

---

## Configuration

All configuration is managed from the dashboard and saved to `config.json`. No environment variables needed.

| Field | Description |
|---|---|
| Callsign | Your amateur radio callsign |
| Locator | Maidenhead locator — auto-calculates lat/lon |
| Log type | HRD XML / Swisslog MDB / Log4OM SQLite / ADIF |
| Log file/directory | Path to your log file or XML directory |
| Refresh interval | Log reload interval in minutes |
| Cluster host | DX Cluster hostname |
| Cluster port | TCP port |
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

---

## Repository structure

```
/
├── app/                    # Docker app source
│   ├── main.py
│   ├── log_readers.py
│   ├── band_plans.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── templates/
│       └── dashboard.html
├── windows/                # Windows build source
│   ├── main_windows.py
│   ├── log_readers.py
│   ├── band_plans.py
│   ├── dx_monitor.spec
│   ├── generar_ico.py
│   ├── compilar.bat
│   ├── requirements_windows.txt
│   ├── static/
│   └── templates/
│       └── dashboard.html
├── docker-compose.yml      # End user Docker Compose
└── screenshots/
```

---

73 de EA3TB
