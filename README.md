# DX Monitor Docker

Monitor de DX Cluster con alertas Telegram y dashboard web. Versión Docker del proyecto original DX Monitor (servicio systemd en `/opt/dx_monitor/`). Son proyectos independientes y no interfieren entre sí.

**Indicativo**: EA3TB | **Versión**: v13

---

## Estructura del proyecto

```
/opt/dx_monitor_docker/
├── docker-compose.yml
├── README.md
├── monitor/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt         # requests
│   ├── dx_monitor.py            # script principal
│   └── band_plans.py            # planes IARU R1/R2/R3
└── web/
    ├── Dockerfile
    ├── requirements.txt         # flask, requests
    ├── app.py                   # API Flask puerto 8765
    ├── static/
    └── templates/
        └── dashboard.html       # Dashboard ES/EN, dark/light
```

### Paths en tiempo de ejecución

| Path (dentro del contenedor) | Descripción |
|---|---|
| `/app/` | Fuentes copiados por Docker en el build (WORKDIR) |
| `/hostfs/` | Filesystem completo del host montado en solo lectura |
| `/opt/dx_monitor_docker/` | Volumen `dx_docker_data` — datos persistentes |

### Datos persistentes (volumen `dx_docker_data`)

| Fichero | Escribe | Lee | Descripción |
|---|---|---|---|
| `config.json` | monitor / web | monitor / web | Configuración completa |
| `flags.json` | monitor / web | monitor / web | Filtros de alerta |
| `status.json` | monitor | web | Estado en tiempo real |
| `dx_monitor.log` | monitor | web | Log del servicio |
| `cty.dat` | monitor | monitor | Base de datos DXCC |
| `cmd.json` | web | monitor | Canal de comandos connect/disconnect |

---

## Instalación

### Primera vez

```bash
cd /opt/dx_monitor_docker
docker compose build --no-cache
docker compose up -d
```

Al arrancar por primera vez todos los campos de configuración están vacíos. Accede al dashboard en `http://<ip-nas>:8765` y rellena la configuración.

### Rebuild tras cambios

```bash
# Solo dashboard HTML — sin rebuild (segundos)
docker cp ./web/templates/dashboard.html dx_web_docker:/app/templates/dashboard.html
docker restart dx_web_docker

# Rebuild parcial web (app.py cambia)
docker compose build --no-cache web && docker compose up -d

# Rebuild parcial monitor (dx_monitor.py cambia)
docker compose build --no-cache monitor && docker compose up -d

# Rebuild completo
docker compose build --no-cache && docker compose up -d
```

> Usar siempre `--no-cache` para evitar capas antiguas.

### Migración desde versión anterior

```bash
docker compose down
docker run --rm \
  -v dx_data:/old \
  -v dx_docker_data:/new \
  alpine sh -c "cp -av /old/. /new/"
docker compose build --no-cache && docker compose up -d
```

---

## Configuración

Toda la configuración se gestiona desde el dashboard y se persiste en `config.json`. No hay variables de entorno que mantener.

| Campo | Descripción |
|---|---|
| Indicativo | Indicativo de radioaficionado |
| Locator | Locator Maidenhead — calcula lat/lon automáticamente |
| Directorio XML | Path en el host al directorio con XMLs de HRD — explorable desde el dashboard |
| Cluster Host | Host del DX Cluster |
| Cluster Port | Puerto TCP |
| Cluster Login | Indicativo de login |
| Cluster Password | Contraseña (campo ocultable con botón 👁) |
| Bot Token | Token del bot de Telegram (campo ocultable con botón 👁) |
| Chat ID | ID del chat de Telegram |
| Idioma alertas | Español / English |
| Zona horaria | Selector con 40+ zonas agrupadas por región + campo manual para cualquier zona IANA |
| Hora | Local (según timezone) / UTC |

---

## Filtros de alerta

Configurables desde el dashboard, guardados en `flags.json`:

- **Zona IARU**: R1 (Europa/África), R2 (Américas), R3 (Asia-Pacífico)
- **Bandas activas**: selección individual o todo/nada
- **Modos activos**: CW, SSB, RTTY, FT8, FT4
- **Tipos de alerta**:
  - País nuevo — DXCC nunca trabajado
  - País trabajado — trabajado pero sin QSL
  - Banda nueva — DXCC en banda no trabajada
  - Banda sin QSL — banda trabajada, QSL pendiente
  - Modo nuevo — DXCC/banda en modo no trabajado
  - Modo sin QSL — modo trabajado, QSL pendiente

---

## Cluster connect / disconnect

El botón **Conectar** del dashboard escribe un comando en `cmd.json` que `dx_monitor.py` lee en su bucle principal. Al arrancar el contenedor:

- Si hay `cluster_host` y `cluster_login` configurados → conecta automáticamente
- Si los campos están vacíos → espera a que el usuario configure y pulse Conectar

---

## Alertas en tiempo real (SSE)

Las alertas aparecen en el dashboard instantáneamente mediante **Server-Sent Events**. `app.py` vigila `status.json` cada 0.5s y empuja los cambios a todos los clientes conectados. El polling de 10s solo actualiza stats, log y estado del cluster. Si se pierde la conexión SSE el dashboard reconecta automáticamente tras 5s.

---

## Comandos útiles

```bash
# Logs en tiempo real
docker logs -f dx_monitor_docker
docker logs -f dx_web_docker

# Estado contenedores
docker compose ps

# Parar / arrancar
docker compose down
docker compose up -d

# Acceder al contenedor monitor
docker exec -it dx_monitor_docker bash

# Ver datos persistentes
docker exec dx_monitor_docker ls -la /opt/dx_monitor_docker/

# Ver config activa
docker exec dx_monitor_docker cat /opt/dx_monitor_docker/config.json
```

---

## Coexistencia con el servicio systemd

- **Servicio original**: `/opt/dx_monitor/` en el host, gestionado por systemd
- **Docker**: `/opt/dx_monitor_docker/` en el host, volumen interno `dx_docker_data`

No arrancar ambos simultáneamente apuntando al mismo cluster con el mismo login.

---

73 de EA3TB
