"""Pruebas del historial CSV y del informe Excel."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import exportar  # noqa: E402
import historial  # noqa: E402

TIENDA = "Didácticas Electrónicas"


def cand(veredicto, precio, dif, url, nombre="Conversor"):
    return {"nombre": nombre, "sku": "X1", "precio": precio, "precio_con_iva": precio * 1.19, "iva_incluido": False,
            "url": url, "veredicto": veredicto, "diferencia_pct": dif, "puntajes": {"total": 80}}


def prod(pid, cands, tienda=TIENDA):
    return {"id": pid, "generado": "2026-01-02T10:00:00+00:00",
            "referencia": {"sku": "S" + pid, "nombre": "Prod " + pid, "precio_con_iva": 10000},
            "competidores": [{"tienda": tienda, "estado": "ok", "candidatos": cands}]}


PRODUCTOS = [
    prod("a", [cand("mismo", 8000, 5.0, "http://x/a"), cand("distinto", 1, 1, "http://x/z")]),
    prod("b", [cand("posible", 9000, -10.0, "http://x/b")]),
    prod("c", [cand("distinto", 5000, 0, "http://x/c")]),
    prod("d", []),
    prod("e", [cand("alternativa", 7000, 1.0, "http://x/e")]),
]


def test_resumen_y_mejores():
    r = exportar.resumen(PRODUCTOS)[TIENDA]
    assert r["comparados"] == 5 and r["con_coincidencia"] == 2
    assert r["diferencia_promedio_pct"] == -2.5
    assert (r["suconel_mas_barato"], r["suconel_mas_caro"], r["igual"]) == (1, 1, 0)
    assert [f["id"] for f in exportar.mejores(PRODUCTOS)] == ["a", "b", "e"]


def test_registrar_sin_duplicar(tmp_path):
    ruta = tmp_path / "h.csv"
    assert historial.registrar(PRODUCTOS, ruta, "2026-01-02T10:00:00+00:00") == 5
    assert historial.registrar(PRODUCTOS, ruta, "2026-01-02T20:00:00+00:00") == 0
    assert historial.registrar(PRODUCTOS, ruta, "2026-01-03T10:00:00+00:00") == 5
    filas = list(csv.DictReader(ruta.open(encoding="utf-8")))
    assert list(filas[0]) == historial.COLUMNAS and len(filas) == 10
    assert not any(f["url_competidor"] == "http://x/z" for f in filas)
    vacia = next(f for f in filas if f["id"] == "d")
    assert vacia["veredicto"] == "sin_resultado" and vacia["precio_competidor"] == ""


def test_excel(tmp_path):
    from openpyxl import load_workbook
    precios = tmp_path / "precios.json"
    precios.write_text(json.dumps({"productos": PRODUCTOS}), encoding="utf-8")
    csv_ = tmp_path / "h.csv"
    historial.registrar(PRODUCTOS, csv_, "2026-01-02T10:00:00+00:00")
    salida = exportar.generar(precios, csv_, tmp_path / "sub" / "i.xlsx")
    wb = load_workbook(salida)
    assert wb.sheetnames == ["Resumen", "Comparación", "Historial"]
    res = wb["Resumen"]
    assert res["A1"].font.bold and res["A2"].value == TIENDA and res["B2"].value == 5 and res["D2"].value == -2.5
    comp = wb["Comparación"]
    assert comp.max_row == 4 and comp["K2"].value == 8000 and comp["K2"].number_format == "#,##0"
    assert wb["Historial"].max_row == 6 and wb["Historial"]["K2"].value == 8000
