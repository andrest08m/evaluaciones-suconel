"""Exporta el estudio de mercado a Excel.

Uso (desde la raíz del repositorio):
    python comparador/scraper/exportar.py [--salida comparador/data/informe.xlsx]

Lee comparador/data/precios.json y comparador/data/historial.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from historial import COLUMNAS, VEREDICTOS_VALIDOS, fila_firestore

RAIZ = Path(__file__).resolve().parents[1]
PRECIOS = RAIZ / "data" / "precios.json"
HISTORIAL = RAIZ / "data" / "historial.csv"
SALIDA = RAIZ / "data" / "informe.xlsx"
TOLERANCIA_PCT = 2.0
COLUMNAS_PRECIO = {"precio_suconel_con_iva", "precio_competidor", "precio_competidor_con_iva"}


def mejor_candidato(res: dict) -> dict | None:
    """Primer candidato que no sea «distinto» (ya vienen ordenados de mejor a peor)."""
    return next((c for c in res.get("candidatos", []) if c.get("veredicto") in VEREDICTOS_VALIDOS), None)


def mejores(productos: list[dict]) -> list[dict]:
    """Una fila (columnas del historial) por mejor candidato de cada tienda y producto."""
    filas = []
    for p in productos:
        fecha = (p.get("generado") or "")[:10]
        for res in p.get("competidores", []):
            c = mejor_candidato(res)
            if c:
                filas.append(fila_firestore(p, res, c, fecha))
    return filas


def resumen(productos: list[dict]) -> dict:
    """Por tienda: comparados, con coincidencia (mismo/posible), diferencia promedio y barato/caro/igual.

    diferencia_pct > 0 significa que Suconel es más barato."""
    out: dict[str, dict] = {}
    for p in productos:
        for res in p.get("competidores", []):
            r = out.setdefault(res["tienda"], {"comparados": 0, "con_coincidencia": 0, "diferencias": [],
                                               "suconel_mas_barato": 0, "suconel_mas_caro": 0, "igual": 0})
            r["comparados"] += 1
            c = mejor_candidato(res)
            if not c or c["veredicto"] == "alternativa":
                continue
            r["con_coincidencia"] += 1
            d = c.get("diferencia_pct")
            if d is None:
                continue
            r["diferencias"].append(d)
            if d > TOLERANCIA_PCT:
                r["suconel_mas_barato"] += 1
            elif d < -TOLERANCIA_PCT:
                r["suconel_mas_caro"] += 1
            else:
                r["igual"] += 1
    for r in out.values():
        ds = r.pop("diferencias")
        r["diferencia_promedio_pct"] = round(sum(ds) / len(ds), 1) if ds else None
    return out


def _num(v: str):
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def _hoja(ws, encabezados, filas, anchos=None, precios=()):
    from openpyxl.styles import Font
    ws.append(encabezados)
    for c in ws[1]:
        c.font = Font(bold=True)
    for f in filas:
        ws.append(f)
    for i, h in enumerate(encabezados, 1):
        letra = ws.cell(row=1, column=i).column_letter
        ws.column_dimensions[letra].width = (anchos or {}).get(h, max(12, min(len(h) + 4, 40)))
        if h in precios:
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].number_format = "#,##0"
    ws.freeze_panes = "A2"


def generar(precios: Path, historial: Path, salida: Path) -> Path:
    from openpyxl import Workbook
    datos = json.loads(Path(precios).read_text(encoding="utf-8")) if Path(precios).exists() else {"productos": []}
    productos = datos.get("productos", [])
    wb = Workbook()

    ws = wb.active
    ws.title = "Resumen"
    enc = ["Tienda", "Productos comparados", "Con coincidencia", "Diferencia promedio (%)",
           "Suconel más barato", "Suconel más caro", "Igual (±2 %)"]
    filas = [[t, r["comparados"], r["con_coincidencia"], r["diferencia_promedio_pct"],
              r["suconel_mas_barato"], r["suconel_mas_caro"], r["igual"]] for t, r in resumen(productos).items()]
    _hoja(ws, enc, filas, {"Tienda": 30, "Productos comparados": 22, "Con coincidencia": 18,
                           "Diferencia promedio (%)": 24, "Suconel más barato": 20, "Suconel más caro": 18, "Igual (±2 %)": 14})

    anchos = {"nombre_suconel": 45, "nombre_competidor": 45, "url_competidor": 50, "tienda": 24, "fecha": 22}
    ws = wb.create_sheet("Comparación")
    _hoja(ws, COLUMNAS, [[f[c] if f[c] is not None else "" for c in COLUMNAS] for f in mejores(productos)],
          anchos, COLUMNAS_PRECIO)

    ws = wb.create_sheet("Historial")
    filas = []
    if Path(historial).exists():
        with Path(historial).open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                filas.append([_num(r[c]) if c in COLUMNAS_PRECIO | {"diferencia_pct", "puntaje_total"} and r.get(c)
                              else r.get(c, "") for c in COLUMNAS])
    _hoja(ws, COLUMNAS, filas, anchos, COLUMNAS_PRECIO)

    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    return Path(salida)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genera el informe Excel del comparador de precios.")
    ap.add_argument("--salida", default=str(SALIDA), help="archivo .xlsx de salida")
    a = ap.parse_args(argv)
    ruta = generar(PRECIOS, HISTORIAL, Path(a.salida))
    print(f"✓ {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
