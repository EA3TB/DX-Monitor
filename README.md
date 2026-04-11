# DX Monitor — EA3TB

DX Cluster monitor with Telegram alerts and web dashboard.
Available for **Windows** (standalone executable) and **Docker** (NAS / Linux).

---

## Features

- DX Cluster connection via CC11 (VE7CC) and standard telnet protocols
- Configurable Telegram alerts: new country, new band, new mode, QSL pending
- Automatic mode inference by frequency (FT8, FT4, CW, SSB) with -1/+3 kHz tolerance
- Bilingual web dashboard (ES/EN), dark/light theme
- Filters by IARU region (R1/R2/R3), bands and modes
- SP/LP azimuth and distance calculated from your Maidenhead locator
- Real-time service log with weekly rotation
- Compatible with Ham Radio Deluxe (HRD) XML log exports

---

## Windows Version

### Download

Download the executable from [Releases](https://github.com/ea3tb/dx-monitor/releases/latest):

```
DXMonitor.exe
```

No Python or any additional dependency required.

### Usage

1. Double-click `DXMonitor.exe`
2. Your browser opens automatically at `http://127.0.0.1:8765`
3. Fill in the configuration from the dashboard
4. Click **Connect**

The program stays active in the system tray.
To close it: right-click the tray icon → **Stop DX Monitor**.

Persistent data (`config.json`, `flags.json`, `dx_monitor.log`, `cty.dat`) is saved next to the `.exe`.

### Build from source

```powershell
cd windows
pip install flask requests pyinstaller tzdata pystray Pillow
python generar_ico.py
pyinstaller dx_monitor.spec --clean
```

The executable is generated at `dist\DXMonitor.exe`.

---

## Docker Version

### Quick install

Create a `docker-compose.yml` file with the contents of `docker/docker-compose.yml` and run:

```bash
docker compose up -d
```

Access the dashboard at `http://<server-ip>:8765`.

### Docker Hub image

```
ea3tb/dx-monitor:latest
```

### Update

```bash
docker rmi -f ea3tb/dx-monitor:latest
docker compose up -d
```

### Build from source

```bash
cd docker
docker build --no-cache -t ea3tb/dx-monitor:latest .
docker push ea3tb/dx-monitor:latest
```

---

## Configuration

All configuration is managed from the dashboard and persisted in `config.json`.

| Field | Description |
|---|---|
| Callsign | Your amateur radio callsign |
| Locator | Maidenhead locator — lat/lon calculated automatically |
| XML directory | Path to the directory containing HRD XML exports |
| Cluster Host | DX Cluster hostname |
| Cluster Port | TCP port |
| Cluster Login | Login callsign |
| Cluster Password | Password |
| Bot Token | Telegram bot token |
| Chat ID | Telegram chat ID |
| Alert language | Spanish / English |
| Timezone | Selector with 40+ zones |
| Time display | Local / UTC |

---

## Alert filters

- **IARU Zone**: R1 (Europe/Africa), R2 (Americas), R3 (Asia-Pacific)
- **Active bands**: individual selection or all/none (160m–23cm)
- **Active modes**: CW, SSB, RTTY, FT8, FT4
- **Alert types**: New country, Worked country, New band, Band no QSL, New mode, Mode no QSL

---

## Mode inference logic

1. If the spot comment explicitly contains CW/SSB/RTTY/FT8/FT4 → that mode is used
2. If no mode in comment and frequency matches a standard FT8/FT4 frequency (-1/+3 kHz) → FT8 or FT4 inferred
3. If no mode and frequency is not FT8/FT4 → CW or SSB inferred from band plan, never RTTY
4. If the segment is exclusively CW → CW is forced

---

## Requirements

**Windows**: 64-bit Windows 10/11. Only the `.exe` is needed.

**Docker**: any host with Docker installed (NAS, Raspberry Pi, Linux server, etc.).
The container mounts the host filesystem at `/hostfs:ro` to access HRD XML files.

---

## Project structure

```
dx-monitor/
├── windows/
│   ├── main_windows.py        # Main process (monitor + web)
│   ├── band_plans.py          # IARU band plans R1/R2/R3
│   ├── dx_monitor.spec        # PyInstaller build config
│   ├── generar_ico.py         # Icon generator (run before build)
│   ├── requirements_windows.txt
│   ├── templates/
│   │   └── dashboard.html
│   └── static/
│       └── icon.ico
└── docker/
    ├── main.py                # Main process (monitor + web)
    ├── band_plans.py          # IARU band plans R1/R2/R3
    ├── Dockerfile
    ├── docker-compose.yml     # End-user (Docker Hub image)
    ├── docker-compose.dev.yml # Development (local build)
    ├── requirements.txt
    └── templates/
        └── dashboard.html
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

73 de EA3TB
