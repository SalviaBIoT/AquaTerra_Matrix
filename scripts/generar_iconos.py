"""Genera los íconos oficiales de AquaTerra Matrix (ICO multi-resolución y PNGs PWA)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
SVG_OFICIAL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#0A0E0C"/>
  <path
    d="M16 5C16 5 8 13.4 8 19.5a8 8 0 0 0 16 0C24 13.4 16 5 16 5Z"
    fill="#34D399" fill-opacity="0.24" stroke="#34D399" stroke-width="2" stroke-linejoin="round"
  />
  <path d="M11.5 21.5c2.5-2.5 5.5-5 9-6.5" stroke="#6EE7B7" stroke-width="2" stroke-linecap="round"/>
</svg>
"""


def renderizar_icono(tamano: int) -> Image.Image:
    """Dibuja el emblema AquaTerra Matrix con supersampling 4x para bordes nítidos."""
    escala = 4
    s = tamano * escala
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo oscuro redondeado (#0A0E0C) con borde sutil esmeralda
    radio = round(s * 0.24)
    margen = max(1, round(s * 0.02))
    draw.rounded_rectangle(
        [margen, margen, s - margen, s - margen],
        radius=radio,
        fill=(10, 14, 12, 255),
        outline=(52, 211, 153, 85),
        width=max(2, round(s * 0.025)),
    )

    # Gota hídrica (#34D399 relleno translúcido + contorno firme)
    cx = s / 2
    top_y = s * 0.16
    bot_cy = s * 0.61
    r = s * 0.255

    # Polígono de la gota: vértice superior + arco inferior suave
    import math

    puntos: list[tuple[float, float]] = [(cx, top_y)]
    for deg in range(-28, 209, 4):
        rad = math.radians(deg)
        px = cx + r * math.cos(rad)
        py = bot_cy + r * math.sin(rad)
        puntos.append((px, py))

    draw.polygon(puntos, fill=(52, 211, 153, 62))
    grosor = max(3, round(s * 0.062))
    draw.line([*puntos, puntos[0]], fill=(52, 211, 153, 255), width=grosor, joint="curve")

    # Nervadura foliar interior (#6EE7B7)
    draw.line(
        [
            (s * 0.365, s * 0.67),
            (s * 0.49, s * 0.56),
            (s * 0.64, s * 0.48),
        ],
        fill=(110, 231, 183, 255),
        width=max(3, round(s * 0.056)),
        joint="curve",
    )

    return img.resize((tamano, tamano), Image.Resampling.LANCZOS)


def main() -> None:
    ruta_ico = RAIZ / "aquaterra" / "ui" / "assets" / "aquaterra.ico"
    ruta_ico.parent.mkdir(parents=True, exist_ok=True)

    base = renderizar_icono(256)
    base.save(
        ruta_ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    public_dir = RAIZ / "frontend" / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    renderizar_icono(192).save(public_dir / "icon-192.png", format="PNG")
    renderizar_icono(512).save(public_dir / "icon-512.png", format="PNG")
    (public_dir / "favicon.svg").write_text(SVG_OFICIAL, encoding="utf-8")

    print(f"OK ICO: {ruta_ico}")
    print(f"OK PNG 192/512 + SVG: {public_dir}")


if __name__ == "__main__":
    main()
