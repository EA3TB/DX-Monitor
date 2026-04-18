#!/usr/bin/env python3
"""
Ejecutar en Windows ANTES de compilar con PyInstaller:
    python generar_ico.py
Genera static/icon.ico con 7 resoluciones en formato BMP/PNG correcto para Windows.
"""
from PIL import Image, ImageDraw, ImageFont
import struct, io, os, sys

def dibujar(size):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size / 64.0
    def p(x, y): return (round(x*s), round(y*s))
    def pw(w):   return max(1, round(w*s))

    # Fondo redondeado
    draw.rounded_rectangle([0, 0, size-1, size-1],
                           radius=max(2, round(10*s)), fill=(15, 21, 32, 255))
    # Mastil
    draw.line([p(32, 8),  p(32, 48)], fill=(200, 218, 240, 255), width=pw(2))
    # Brazo largo — cima
    draw.line([p(8,  8),  p(56,  8)], fill=(200, 218, 240, 255), width=pw(3))
    # Brazo medio
    draw.line([p(14, 22), p(50, 22)], fill=(200, 218, 240, 255), width=pw(2))
    # Brazo corto
    draw.line([p(20, 36), p(44, 36)], fill=(200, 218, 240, 255), width=pw(2))
    # Base
    for coords, fill in [
        ([round(28*s), round(48*s), round(36*s), round(51*s)], (122, 154, 184, 255)),
        ([round(24*s), round(51*s), round(40*s), round(54*s)], (122, 154, 184, 255)),
    ]:
        if coords[2] > coords[0] and coords[3] > coords[1]:
            draw.rounded_rectangle(coords, radius=1, fill=fill)
    # Ondas izquierda
    draw.arc([round(5*s), round(4*s),  round(17*s), round(20*s)],
             270, 90, fill=(0, 212, 255, 140), width=pw(2))
    draw.arc([round(1*s), round(1*s),  round(14*s), round(23*s)],
             270, 90, fill=(0, 212, 255, 75),  width=pw(2))
    # Ondas derecha
    draw.arc([round(47*s), round(4*s), round(59*s), round(20*s)],
             90, 270, fill=(0, 212, 255, 140), width=pw(2))
    draw.arc([round(50*s), round(1*s), round(63*s), round(23*s)],
             90, 270, fill=(0, 212, 255, 75),  width=pw(2))
    # Punto activo
    cx, cy = round(54*s), round(57*s)
    cr, cr2 = max(2, round(4.5*s)), max(1, round(2*s))
    draw.ellipse([cx-cr,  cy-cr,  cx+cr,  cy+cr],  fill=(0, 204, 128, 255))
    draw.ellipse([cx-cr2, cy-cr2, cx+cr2, cy+cr2], fill=(0, 255, 153, 255))
    # Texto DX
    if size >= 24:
        try:
            fs = max(7, round(9*s))
            font = None
            for fname in ["courbd.ttf", "cour.ttf", "consola.ttf", "lucon.ttf"]:
                try:
                    font = ImageFont.truetype(fname, fs)
                    break
                except Exception:
                    pass
            if font is None:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "DX", font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((size - tw) // 2, round(53*s)), "DX",
                      fill=(0, 212, 255, 255), font=font)
        except Exception:
            pass
    return img

def img_to_bmp_ico(img):
    """Convierte RGBA a BMP dentro de ICO (BITMAPINFOHEADER + XOR mask + AND mask)."""
    w, h = img.size
    bih = struct.pack("<IiiHHIIiiII",
        40, w, h*2, 1, 32, 0, 0, 0, 0, 0, 0)
    rgba = img.tobytes("raw", "BGRA")
    # Invertir filas (BMP es bottom-up)
    row_bytes = w * 4
    rows = [rgba[i*row_bytes:(i+1)*row_bytes] for i in range(h)]
    xor = b"".join(reversed(rows))
    # AND mask: todos ceros (usamos alfa del canal BGRA)
    and_row = ((w + 31) // 32) * 4
    and_mask = bytes(and_row * h)
    return bih + xor + and_mask

def img_to_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()

def generar():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    entries = []
    for sz in sizes:
        img  = dibujar(sz)
        # BMP para tamanhos <= 48 (mejor compatibilidad Windows), PNG para los grandes
        data = img_to_bmp_ico(img) if sz <= 48 else img_to_png(img)
        entries.append((sz, data))
        print(f"  {sz:3}x{sz}: {len(data):6} bytes ({'BMP' if sz<=48 else 'PNG'})")

    n = len(entries)
    out = struct.pack("<HHH", 0, 1, n)
    offset = 6 + n * 16
    for sz, data in entries:
        w = sz if sz < 256 else 0
        h = sz if sz < 256 else 0
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in entries:
        out += data

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "icon.ico")
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"\nicon.ico generado: {out_path} ({len(out)/1024:.1f} KB)")
    return out_path

if __name__ == "__main__":
    print("Generando icon.ico...")
    path = generar()
    # Verificar
    try:
        ico = Image.open(path)
        ico.load()
        print(f"Verificacion OK: {ico.size}, mode={ico.mode}")
    except Exception as e:
        print(f"Error de verificacion: {e}")
        sys.exit(1)
    print("\nAhora ejecuta: pyinstaller dx_monitor.spec --clean")
