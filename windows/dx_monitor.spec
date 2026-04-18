# dx_monitor.spec  -  PyInstaller spec para DX Monitor Windows
# Uso: pyinstaller dx_monitor.spec --clean

block_cipher = None

from PyInstaller.utils.hooks import collect_all
import os

pil_datas,  pil_binaries,  pil_hiddenimports  = collect_all('PIL')
tray_datas, tray_binaries, tray_hiddenimports = collect_all('pystray')

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
ICON_PATH = os.path.join(SPEC_DIR, 'static', 'icon.ico')

a = Analysis(
    ['main_windows.py'],
    pathex=[SPEC_DIR],
    binaries=[*pil_binaries, *tray_binaries],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
        *pil_datas,
        *tray_datas,
    ],
    hiddenimports=[
        'zoneinfo',
        'zoneinfo._czoneinfo',
        'tzdata',
        'flask',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'requests',
        'certifi',
        'urllib3',
        'charset_normalizer',
        'idna',
        'logging.handlers',
        'xml.etree.ElementTree',
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        *pil_hiddenimports,
        *tray_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas',
        'cv2', 'scipy', 'test', 'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DXMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)
