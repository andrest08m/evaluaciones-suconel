"""Electronilab: lectura de página, búsqueda y comparación con Suconel (sin red)."""
import sys
from pathlib import Path

import httpx

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

from coincidencia import coincidencia_fuerte, combinar, extraer_specs, puntaje_descripcion, puntaje_specs  # noqa: E402
from tiendas import electronilab, suconel  # noqa: E402
from tiendas.base import Cliente  # noqa: E402

PAG = AQUI / "paginas"
U_EL = "https://electronilab.co/tienda/modulo-lm2596-convertidor-de-voltaje-dc-dc-buck-1-25v-35v"
U_SUC = "https://suconel.com/productos/modulo-regulador-dc-dc-ajustable-lm-2596"


def leer(mod, archivo, url):
    p = mod.leer((PAG / archivo).read_text(encoding="utf-8"), url)
    p.specs = extraer_specs(p.nombre, p.descripcion, p.sku, p.url)
    return p


def test_leer_electronilab():
    p = leer(electronilab, "electronilab_lm2596.html", U_EL)
    assert p.nombre == "Módulo LM2596 Convertidor de Voltaje DC-DC Reductor Buck 1.25V-35V"
    assert p.sku.startswith("FUM0002")
    assert p.precio == 6900 and p.iva_incluido is True and p.precio_con_iva() == 6900
    assert p.imagen.endswith("Modulo-LM2596-convertidor-buck.jpg")
    assert "43*20*14mm" in p.descripcion and "HLK-PM01" not in p.descripcion
    assert p.specs["corriente_a"] == 3 and p.specs["frecuencia_khz"] == 150


def test_busqueda_html():
    enl = electronilab.urls_de_busqueda((PAG / "electronilab_busqueda.html").read_text(encoding="utf-8"))
    assert [str(e) for e in enl] == [
        "https://electronilab.co/tienda/modulo-lm2596-convertidor-de-voltaje-dc-dc-buck-1-25v-35v/",
        "https://electronilab.co/tienda/lm2596-hw-411-modulo-regulador-con-display/",
        "https://electronilab.co/tienda/xl4015-convertidor-buck-5a/"]
    assert "LM2596" in enl[0].texto and "6,900" in enl[0].texto


def _cliente(manejar):
    c = Cliente(firecrawl_key="")
    c.http = httpx.Client(transport=httpx.MockTransport(manejar))
    c._esperar = lambda url: None
    return c


def test_buscar_api_json():
    def manejar(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        assert req.url.path == "/wp-json/wc/store/v1/products"
        return httpx.Response(200, json=[{"id": 1, "name": "Módulo LM2596", "permalink": U_EL, "sku": "FUM0002",
                                          "prices": {"price": "690000"}, "images": [{"src": "x.jpg"}]}])
    enl = electronilab.buscar(_cliente(manejar), "LM2596")
    assert enl == [U_EL] and "FUM0002" in enl[0].texto and "6,900" in enl[0].texto


def test_buscar_cae_a_html():
    html = (PAG / "electronilab_busqueda.html").read_text(encoding="utf-8")

    def manejar(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path.startswith("/wp-json"):
            return httpx.Response(200, text="<html>no es json</html>")
        assert req.url.params["post_type"] == "product"
        return httpx.Response(200, text=html)
    assert len(electronilab.buscar(_cliente(manejar), "LM2596")) == 3


def test_lm2596_electronilab_vs_suconel():
    ref = leer(suconel, "suconel_lm2596.html", U_SUC)
    cand = leer(electronilab, "electronilab_lm2596.html", U_EL)
    ps, _, conflicto = puntaje_specs(ref.specs, cand.specs)
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, cand.nombre, cand.descripcion)
    fuerte = coincidencia_fuerte(ref.specs, cand.specs, ps, ref.sku, cand.sku, ref.nombre, cand.nombre)
    total, veredicto = combinar(ps, pd, None, conflicto, fuerte)
    # Mismo chip, mismo modelo, 150 kHz y medidas casi iguales; la única diferencia es 2 A vs 3 A,
    # que coincidencia.py trata como conflicto (por eso "alternativa" y no "mismo"/"posible").
    assert fuerte and total >= 80
    assert veredicto in ("mismo", "posible", "alternativa")
    assert combinar(ps, pd, None, False, fuerte)[1] == "mismo"   # sin ese conflicto sería el mismo producto
