"""Mercado Libre: API simulada con httpx.MockTransport (sin red)."""
import sys
from pathlib import Path

import httpx
import pytest

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

from coincidencia import coincidencia_fuerte, combinar, extraer_specs, puntaje_descripcion, puntaje_specs  # noqa: E402
from tiendas import mercadolibre as ml, suconel  # noqa: E402
from tiendas.base import Cliente  # noqa: E402

U_SUC = "https://suconel.com/productos/modulo-regulador-dc-dc-ajustable-lm-2596"


def item(i, titulo, precio, cond="new", **kw):
    d = {"id": f"MCO{i}", "title": titulo, "price": precio, "currency_id": "COP",
         "permalink": f"https://articulo.mercadolibre.com.co/MCO-{i}-x-_JM", "condition": cond,
         "thumbnail": f"https://http2.mlstatic.com/D_{i}-I.jpg", "seller": {"nickname": "TIENDA_X"},
         "shipping": {"free_shipping": False}, "attributes": []}
    d.update(kw)
    return d


LM = item(111, "Módulo LM2596 Convertidor Buck Dc-dc 3a", 8500, attributes=[
    {"id": "BRAND", "name": "Marca", "value_name": "Genérica"},
    {"id": "MODEL", "name": "Modelo", "value_name": "LM2596"},
    {"id": "INPUT_VOLTAGE", "name": "Voltaje de entrada", "value_name": "4.5-40 V"},
    {"id": "OUTPUT_CURRENT", "name": "Corriente de salida", "value_name": "3 A"}])


@pytest.fixture(autouse=True)
def limpiar():
    ml._items.clear()


def cliente(resultados=None, llamadas=None):
    def manejar(req):
        if llamadas is not None:
            llamadas.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/sites/MCO/search":
            assert req.url.params["q"] == "LM2596"
            return httpx.Response(200, json={"results": resultados})
        if req.url.path == "/items/MCO111":
            return httpx.Response(200, json=LM)
        return httpx.Response(404)
    c = Cliente(firecrawl_key="")
    c.http = httpx.Client(transport=httpx.MockTransport(manejar))
    c._esperar = lambda url: None
    return c


def test_buscar_filtra_usados_duplicados_y_ordena():
    res = [item(1, "Módulo  LM2596 Buck", 12000), item(2, "Modulo lm2596 buck", 9000),
           item(3, "LM2596 usado", 1000, cond="used"), item(4, "LM2596 con Display", 7000)]
    enl = ml.buscar(cliente(res), "LM2596")
    assert [e.texto for e in enl] == ["LM2596 con Display", "Modulo lm2596 buck"]   # 1 por título, por precio
    assert all(str(e) in ml._items for e in enl)


def test_leer_desde_cache_sin_red():
    llamadas = []
    cli = cliente([LM], llamadas)
    (e,) = ml.buscar(cli, "LM2596")
    n = len(llamadas)
    p = ml.leer_url(cli, e)
    assert len(llamadas) == n                      # no hubo más peticiones
    assert p.precio == 8500 and p.iva_incluido is True and p.sku == "LM2596"
    assert p.imagen.endswith("D_111-O.jpg")
    assert "Voltaje de entrada: 4.5-40 V" in p.descripcion and "Vendedor: TIENDA_X" in p.descripcion
    assert p.descripcion.splitlines()[-1] == "Nuevo"


def test_leer_url_fuera_de_cache_pide_items():
    llamadas = []
    p = ml.leer_url(cliente(None, llamadas), LM["permalink"])
    assert "/items/MCO111" in llamadas and p.nombre == LM["title"]


def test_sku_por_defecto_es_el_id():
    assert ml.desde_item(item(5, "Algo", 1), "u").sku == "MCO5"


def test_lm2596_ml_vs_suconel():
    ref = suconel.leer((AQUI / "paginas/suconel_lm2596.html").read_text(encoding="utf-8"), U_SUC)
    ref.specs = extraer_specs(ref.nombre, ref.descripcion, ref.sku, ref.url)
    cand = ml.desde_item(LM, LM["permalink"])
    cand.specs = extraer_specs(cand.nombre, cand.descripcion, cand.sku, cand.url)
    ps, _, conflicto = puntaje_specs(ref.specs, cand.specs)
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, cand.nombre, cand.descripcion)
    fuerte = coincidencia_fuerte(ref.specs, cand.specs, ps, ref.sku, cand.sku, ref.nombre, cand.nombre)
    total, veredicto = combinar(ps, pd, None, conflicto, fuerte)
    # Mismo chip, mismo modelo, 150 kHz y medidas casi iguales; la única diferencia es 2 A vs 3 A,
    # que coincidencia.py trata como conflicto (por eso "alternativa" y no "mismo"/"posible").
    assert fuerte and total >= 80
    assert veredicto in ("mismo", "posible", "alternativa")
    assert combinar(ps, pd, None, False, fuerte)[1] == "mismo"   # sin ese conflicto sería el mismo producto
