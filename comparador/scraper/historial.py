"""Historial de precios para el estudio de mercado.

`registrar` agrega al CSV (comparador/data/historial.csv) una fila por producto, tienda y candidato,
una vez por día. `fila_firestore` da la misma fila como dict para guardarla en Firestore.
"""
from __future__ import annotations

import csv
from pathlib import Path

COLUMNAS = ["fecha", "id", "categoria", "sku_suconel", "nombre_suconel", "precio_suconel_con_iva",
            "tienda", "veredicto", "sku_competidor", "nombre_competidor", "precio_competidor",
            "precio_competidor_con_iva", "iva_incluido", "diferencia_pct", "puntaje_total", "url_competidor"]
VEREDICTOS_VALIDOS = ("mismo", "posible", "alternativa")


def fila_firestore(producto: dict, tienda_res: dict, cand: dict | None, fecha_iso: str) -> dict:
    """Fila del historial (mismos campos que el CSV). Con cand=None queda como «sin_resultado»."""
    ref = producto.get("referencia", {})
    fila = {
        "fecha": fecha_iso, "id": producto.get("id", ""), "categoria": producto.get("categoria") or "",
        "sku_suconel": ref.get("sku") or "", "nombre_suconel": ref.get("nombre") or "",
        "precio_suconel_con_iva": ref.get("precio_con_iva"),
        "tienda": tienda_res.get("tienda", ""),
        "veredicto": "sin_resultado", "sku_competidor": "", "nombre_competidor": "",
        "precio_competidor": None, "precio_competidor_con_iva": None, "iva_incluido": None,
        "diferencia_pct": None, "puntaje_total": None, "url_competidor": "",
    }
    if cand:
        fila.update(
            veredicto=cand.get("veredicto", ""), sku_competidor=cand.get("sku") or "",
            nombre_competidor=cand.get("nombre") or "", precio_competidor=cand.get("precio"),
            precio_competidor_con_iva=cand.get("precio_con_iva"), iva_incluido=cand.get("iva_incluido"),
            diferencia_pct=cand.get("diferencia_pct"),
            puntaje_total=(cand.get("puntajes") or {}).get("total"), url_competidor=cand.get("url") or "")
    return fila


def filas_producto(producto: dict, fecha_iso: str) -> list[dict]:
    filas = []
    for res in producto.get("competidores", []):
        cands = [c for c in res.get("candidatos", []) if c.get("veredicto") in VEREDICTOS_VALIDOS]
        if cands:
            filas += [fila_firestore(producto, res, c, fecha_iso) for c in cands]
        else:
            filas.append(fila_firestore(producto, res, None, fecha_iso))
    return filas


def _texto(v) -> str:
    return "" if v is None else str(v)


def registrar(productos: list[dict], ruta_csv: Path, fecha_iso: str) -> int:
    """Agrega las filas nuevas al CSV (lo crea con encabezado si no existe). Devuelve cuántas agregó."""
    ruta_csv = Path(ruta_csv)
    existentes = set()
    if ruta_csv.exists():
        with ruta_csv.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existentes.add((r.get("fecha", "")[:10], r.get("id", ""), r.get("tienda", ""), r.get("url_competidor", "")))
    nuevas = []
    for p in productos:
        for fila in filas_producto(p, fecha_iso):
            clave = (fecha_iso[:10], fila["id"], fila["tienda"], fila["url_competidor"])
            if clave not in existentes:
                existentes.add(clave)
                nuevas.append(fila)
    if not nuevas and ruta_csv.exists():
        return 0
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta_csv.exists()
    with ruta_csv.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(COLUMNAS)
        for fila in nuevas:
            w.writerow([_texto(fila[c]) for c in COLUMNAS])
    return len(nuevas)
