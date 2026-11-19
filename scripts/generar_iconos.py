"""Genera los íconos oficiales de SalviaBIoT (ICO multi-resolución y PNGs PWA)."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
SVG_OFICIAL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#0A0E0C"/>
  <rect x="1" y="1" width="30" height="30" rx="7" fill="none" stroke="#34D399" stroke-opacity="0.35" stroke-width="1"/>
  <path
    d="M16 25V13.5"
    stroke="#34D399" stroke-width="2" stroke-linecap="round"
  />
  <path
    d="M16 14.5C16 9.5 20.2 6.8 25 7.2C24.8 12.2 21.4 15.6 16 14.5Z"
    fill="#34D399" fill-opacity="0.28" stroke="#34D399" stroke-width="1.8" stroke-linejoin="round"
  />
  <path
    d="M16 17.5C16 13.5 12.5 11.2 8 11.6C8.2 15.8 11.3 18.6 16 17.5Z"
    fill="#6EE7B7" fill-opacity="0.22" stroke="#6EE7B7" stroke-width="1.8" stroke-linejoin="round"
  />
  <circle cx="16" cy="25.5" r="2" fill="#6EE7B7"/>
</svg>
"""


def _puntos_hoja(
    x0: float, y0: float, x1: float, y1: float, curva_sup: float, curva_inf: float, pasos: int = 24
) -> list[tuple[float, float]]:
    """Calcula el polígono suave de una hoja botánica mediante curvas cuadráticas de Bézier."""
    pts: list[tuple[float, float]] = []
    mx = (x0 + x1) / 2
    my = (y0 + y1) / 2
    dx = x1 - x0
    dy = y1 - y0
    largo = math.hypot(dx, dy) or 1.0
    nx = -dy / largo
    ny = dx / largo

    cx1 = mx + nx * curva_sup
    cy1 = my + ny * curva_sup
    for i in range(pasos + 1):
        t = i / pasos
        px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx1 + t**2 * x1
        py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy1 + t**2 * y1
        pts.append((px, py))

    cx2 = mx - nx * curva_inf
    cy2 = my - ny * curva_inf
    for i in range(1, pasos):
        t = i / pasos
        px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx2 + t**2 * x0
        py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy2 + t**2 * y0
        pts.append((px, py))
    return pts


def renderizar_icono(tamano: int) -> Image.Image:
    """Dibuja el emblema oficial SalviaBIoT (brote botánico + nodo Bio-IoT) con supersampling 4x."""
    escala = 4
    s = tamano * escala
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo oscuro redondeado (#0A0E0C) con borde esmeralda
    radio = round(s * 0.24)
    margen = max(1, round(s * 0.02))
    draw.rounded_rectangle(
        [margen, margen, s - margen, s - margen],
        radius=radio,
        fill=(10, 14, 12, 255),
        outline=(52, 211, 153, 105),
        width=max(2, round(s * 0.028)),
    )

    grosor = max(3, round(s * 0.056))

    # Tallo central Bio-IoT
    draw.line(
        [(s * 0.50, s * 0.78), (s * 0.50, s * 0.42)],
        fill=(52, 211, 153, 255),
        width=grosor,
    )

    # Hoja derecha principal (#34D399)
    hoja_der = _puntos_hoja(s * 0.50, s * 0.46, s * 0.79, s * 0.22, s * 0.14, s * 0.12)
    draw.polygon(hoja_der, fill=(52, 211, 153, 72))
    draw.line([*hoja_der, hoja_der[0]], fill=(52, 211, 153, 255), width=grosor, joint="curve")

    # Hoja izquierda secundaria (#6EE7B7)
    hoja_izq = _puntos_hoja(s * 0.50, s * 0.55, s * 0.23, s * 0.36, s * 0.11, s * 0.10)
    draw.polygon(hoja_izq, fill=(110, 231, 183, 56))
    draw.line([*hoja_izq, hoja_izq[0]], fill=(110, 231, 183, 255), width=grosor, joint="curve")

    # Nodo sensorial en la raíz del tallo (#6EE7B7)
    r_nodo = s * 0.068
    cx, cy = s * 0.50, s * 0.79
    draw.ellipse(
        [cx - r_nodo, cy - r_nodo, cx + r_nodo, cy + r_nodo],
        fill=(110, 231, 183, 255),
    )

    return img.resize((tamano, tamano), Image.Resampling.LANCZOS)


def main() -> None:
    assets_dir = RAIZ / "aquaterra" / "ui" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    ruta_salvia_ico = assets_dir / "salviabiot.ico"
    ruta_legacy_ico = assets_dir / "aquaterra.ico"

    base = renderizar_icono(256)
    tamanos = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(ruta_salvia_ico, format="ICO", sizes=tamanos)
    base.save(ruta_legacy_ico, format="ICO", sizes=tamanos)

    public_dir = RAIZ / "frontend" / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    renderizar_icono(192).save(public_dir / "icon-192.png", format="PNG")
    renderizar_icono(512).save(public_dir / "icon-512.png", format="PNG")
    (public_dir / "favicon.svg").write_text(SVG_OFICIAL, encoding="utf-8")

    print(f"OK ICO: {ruta_salvia_ico} (y {ruta_legacy_ico.name})")
    print(f"OK PNG 192/512 + SVG: {public_dir}")


if __name__ == "__main__":
    main()
