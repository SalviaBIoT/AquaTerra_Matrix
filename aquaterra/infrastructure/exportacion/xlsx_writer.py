"""Escritor y lector ligero de libros OpenXML (``.xlsx``) con la biblioteca estándar de Python.

Genera archivos ``.xlsx`` 100 % compatibles con Microsoft Excel, LibreOffice Calc y Google Sheets
usando únicamente ``zipfile`` y ``xml.etree.ElementTree`` (cero dependencias externas).
Soporta múltiples hojas, encabezados con estilo destacado, celdas numéricas nativas y textos UTF-8.
"""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


@dataclass(frozen=True, slots=True)
class HojaCalculo:
    nombre: str
    encabezados: Sequence[str]
    filas: Sequence[Sequence[Any]]


def _letra_columna(indice_1: int) -> str:
    resultado = []
    n = indice_1
    while n > 0:
        n, resto = divmod(n - 1, 26)
        resultado.append(chr(65 + resto))
    return "".join(reversed(resultado))


def _nombre_hoja_seguro(nombre: str) -> str:
    limpio = "".join(c if c not in r"[]:*?/\\" else "_" for c in nombre.strip())
    return (limpio or "Hoja")[:31]


def _xml_celda(ref: str, valor: Any, *, estilo: int = 0) -> str:
    attr_s = f' s="{estilo}"' if estilo > 0 else ""
    if valor is None or valor == "":
        return f'<c r="{ref}"{attr_s}/>'
    if isinstance(valor, bool):
        texto = "TRUE" if valor else "FALSE"
        return f'<c r="{ref}" t="inlineStr"{attr_s}><is><t>{texto}</t></is></c>'
    if isinstance(valor, (int, float)):
        return f'<c r="{ref}" t="n"{attr_s}><v>{valor}</v></c>'
    texto_esc = escape(str(valor))
    return f'<c r="{ref}" t="inlineStr"{attr_s}><is><t xml:space="preserve">{texto_esc}</t></is></c>'


def _xml_hoja(hoja: HojaCalculo) -> str:
    num_cols = max(len(hoja.encabezados), *(len(f) for f in hoja.filas), 1)
    cols_xml = (
        f'<cols><col min="1" max="{num_cols}" width="20" customWidth="1"/></cols>'
    )
    filas_xml: list[str] = []

    if hoja.encabezados:
        celdas_enc = [
            _xml_celda(f"{_letra_columna(col_idx)}1", titulo, estilo=1)
            for col_idx, titulo in enumerate(hoja.encabezados, start=1)
        ]
        filas_xml.append(f'<row r="1">{"".join(celdas_enc)}</row>')

    offset = 2 if hoja.encabezados else 1
    for idx_fila, fila in enumerate(hoja.filas, start=offset):
        celdas = [
            _xml_celda(f"{_letra_columna(col_idx)}{idx_fila}", valor)
            for col_idx, valor in enumerate(fila, start=1)
        ]
        filas_xml.append(f'<row r="{idx_fila}">{"".join(celdas)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{_NS_MAIN}">'
        f"{cols_xml}"
        f'<sheetData>{"".join(filas_xml)}</sheetData>'
        "</worksheet>"
    )


def escribir_libro_xlsx(ruta_destino: str | Path, hojas: Sequence[HojaCalculo]) -> Path:
    """Escribe un archivo ``.xlsx`` multi-hoja en ``ruta_destino`` y devuelve su ``Path``."""
    if not hojas:
        raise ValueError("El libro .xlsx debe contener al menos una hoja.")

    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    overrides_ct = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(hojas) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides_ct}</Types>"
    )

    rels_raiz = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )

    sheets_wb = "".join(
        f'<sheet name="{escape(_nombre_hoja_seguro(h.nombre))}" sheetId="{i}" r:id="rId{i}"/>'
        for i, h in enumerate(hojas, start=1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_NS_MAIN}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets_wb}</sheets></workbook>"
    )

    rels_sheets = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(hojas) + 1)
    )
    id_styles = len(hojas) + 1
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels_sheets}"
        f'<Relationship Id="rId{id_styles}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{_NS_MAIN}">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        "</fonts>"
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1B4332"/></patternFill></fill>'
        "</fills>"
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        "</cellXfs></styleSheet>"
    )

    with zipfile.ZipFile(destino, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_raiz)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        for i, hoja in enumerate(hojas, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _xml_hoja(hoja))

    return destino


def leer_hojas_xlsx(ruta: str | Path) -> dict[str, list[list[Any]]]:
    """Lee un archivo ``.xlsx`` generado por el sistema y devuelve ``{nombre_hoja: filas}``."""
    ns = {"m": _NS_MAIN, "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    resultado: dict[str, list[list[Any]]] = {}
    with zipfile.ZipFile(ruta, mode="r") as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        mapa_rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        for sheet in wb.findall("m:sheets/m:sheet", ns):
            nombre = sheet.attrib["name"]
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = "xl/" + mapa_rels[rid].lstrip("/")
            raiz_hoja = ET.fromstring(zf.read(target))
            filas_leidas: list[list[Any]] = []
            for row in raiz_hoja.findall("m:sheetData/m:row", ns):
                fila_vals: list[Any] = []
                for c in row.findall("m:c", ns):
                    tipo = c.attrib.get("t", "n")
                    if tipo == "inlineStr":
                        t_el = c.find("m:is/m:t", ns)
                        fila_vals.append(t_el.text if t_el is not None and t_el.text is not None else "")
                    else:
                        v_el = c.find("m:v", ns)
                        if v_el is None or v_el.text is None:
                            fila_vals.append(None)
                        else:
                            num = float(v_el.text)
                            fila_vals.append(int(num) if num.is_integer() else num)
                filas_leidas.append(fila_vals)
            resultado[nombre] = filas_leidas
    return resultado
