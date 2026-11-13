"""Dibuja el ícono de MeshAudit (malla triangulada con una marca de verificación) y lo
guarda como app_mac/icono.icns.   .venv/bin/python app_mac/icono.py"""
import subprocess, tempfile, pathlib
from PIL import Image, ImageDraw

L = 1024
img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((80, 80, L - 80, L - 80), radius=190, fill=(28, 52, 92, 255))
# malla: rejilla triangulada
n, x0, y0, paso = 4, 230, 230, 140
pts = [[(x0 + i * paso, y0 + j * paso) for i in range(n + 1)] for j in range(n + 1)]
for j in range(n):
    for i in range(n):
        a, b, c, e = pts[j][i], pts[j][i + 1], pts[j + 1][i], pts[j + 1][i + 1]
        for tri in ((a, b, e), (a, e, c)):
            d.polygon(tri, outline=(140, 190, 255, 255), width=10)
for fila in pts:
    for p in fila:
        d.ellipse((p[0] - 16, p[1] - 16, p[0] + 16, p[1] + 16), fill=(220, 235, 255, 255))
# marca de verificación
d.ellipse((560, 560, 880, 880), fill=(46, 180, 110, 255))
d.line([(625, 725), (700, 800), (820, 650)], fill="white", width=42, joint="curve")

salida = pathlib.Path(__file__).with_name("icono.icns")
with tempfile.TemporaryDirectory() as t:
    conj = pathlib.Path(t) / "icono.iconset"
    conj.mkdir()
    for lado in (16, 32, 128, 256, 512):
        img.resize((lado, lado), Image.LANCZOS).save(conj / f"icon_{lado}x{lado}.png")
        img.resize((lado * 2, lado * 2), Image.LANCZOS).save(conj / f"icon_{lado}x{lado}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(conj), "-o", str(salida)], check=True)
print(salida)
