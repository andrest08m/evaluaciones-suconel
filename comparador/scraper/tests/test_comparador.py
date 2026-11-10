"""Pruebas con páginas de ejemplo que reproducen el texto real de cada tienda."""
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

from coincidencia import combinar, extraer_specs, puntaje_descripcion, puntaje_specs  # noqa: E402
from tiendas import didacticas, suconel  # noqa: E402
from tiendas.base import precio_cop  # noqa: E402

PAG = AQUI / "paginas"
U_SUC = "https://suconel.com/productos/modulo-regulador-dc-dc-ajustable-lm-2596"
U_DID = "https://www.didacticaselectronicas.com/shop/lm2596-v-5a-conversor-dc-dc-reductor-0-24v-5a-xl4005-6792"
U_XL = "https://www.didacticaselectronicas.com/shop/xl4015-5a-modulo-conversor-dc-dc-xl4015-salida-ajustable-5a-52118"


def leer(mod, archivo, url):
    p = mod.leer((PAG / archivo).read_text(encoding="utf-8"), url)
    p.specs = extraer_specs(p.nombre, p.descripcion, p.sku, p.url)
    return p


def test_precios():
    assert precio_cop("$ 3.135") == 3135
    assert precio_cop("$ 5.654,88") == 5654.88
    assert precio_cop("$ 6,900") == 6900
    assert precio_cop("$ 1.085.736,96") == 1085736.96
    assert precio_cop("3135.5") == 3135.5


def test_suconel():
    p = leer(suconel, "suconel_lm2596.html", U_SUC)
    assert p.nombre == "Módulo Regulador DC-DC Ajustable LM2596"
    assert p.sku == "LM2596"
    assert p.precio == 3135 and p.iva_incluido is False
    assert round(p.precio_con_iva()) == 3731
    assert p.imagen == "https://suconel.com/storage/productos/lm2596.jpg"
    assert "ADXL345" not in p.descripcion
    s = p.specs
    assert s["chips"] == ["LM2596"]
    assert s["corriente_a"] == 2
    assert s["vin"] == [4, 40] and s["vout"] == [1.25, 37]
    assert s["frecuencia_khz"] == 150


def test_didacticas():
    p = leer(didacticas, "didacticas_lm2596_v_5a.html", U_DID)
    assert p.sku == "LM2596-V-5A"
    assert p.nombre == "Conversor DC/DC Reductor 0-24v 5A"
    assert p.precio == 5654.88
    assert p.imagen.endswith("/6792/image_1024")
    s = p.specs
    assert set(s["chips"]) == {"LM2596", "XL4005"}
    assert s["corriente_a"] == 5
    assert s["vin"] == [5, 32] and s["vout"] == [0.8, 24]


def test_busqueda_didacticas():
    urls = didacticas.urls_de_busqueda((PAG / "didacticas_busqueda.html").read_text(encoding="utf-8"))
    assert urls == [U_DID, U_XL]


def test_lm2596_vs_didacticas_no_es_el_mismo():
    ref = leer(suconel, "suconel_lm2596.html", U_SUC)
    for archivo, url in (("didacticas_lm2596_v_5a.html", U_DID), ("didacticas_xl4015.html", U_XL)):
        c = leer(didacticas, archivo, url)
        ps, motivos, conflicto = puntaje_specs(ref.specs, c.specs)
        pd = puntaje_descripcion(ref.nombre, ref.descripcion, c.nombre, c.descripcion)
        total, veredicto = combinar(ps, pd, None, conflicto)
        assert conflicto, motivos
        assert any("corriente distinta" in m for m in motivos)
        assert veredicto in ("alternativa", "distinto")


def test_mismo_producto():
    ref = leer(suconel, "suconel_lm2596.html", U_SUC)
    ps, motivos, conflicto = puntaje_specs(ref.specs, ref.specs)
    total, veredicto = combinar(ps, 100, 100, conflicto)
    assert not conflicto and veredicto == "mismo"


def test_foto():
    import io
    from PIL import Image, ImageDraw
    from coincidencia import puntaje_foto

    def img(forma):
        im = Image.new("RGB", (200, 200), "white")
        d = ImageDraw.Draw(im)
        (d.rectangle if forma == "rect" else d.ellipse)([30, 50, 170, 150], fill=(30, 90, 200))
        b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

    assert puntaje_foto(img("rect"), img("rect")) == 100
    assert puntaje_foto(img("rect"), img("circ")) < 80
    assert puntaje_foto(img("rect"), None) is None
