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


# ---- casos reales que fallaron (10-nov-2026) ----
U_XL6009 = "https://suconel.com/productos/modulo-xl6009-para-elevacion-de-voltaje-estable-dc-dc-boost-de-4a-xl6009"
U_TAR = "https://www.didacticaselectronicas.com/shop/tar-xl6009-conversor-dc-dc-elevador-35v-3a-21004"
U_TAR_D = "https://www.didacticaselectronicas.com/shop/tar-xl6009-disp-conversor-dc-dc-elevador-35v-3a-con-display-52756"


def test_suconel_sku_del_producto_no_de_relacionados():
    p = leer(suconel, "suconel_xl6009.html", U_XL6009)
    assert p.sku == "XL6009"            # por el enlace de WhatsApp (el campo SKU viene vacío)
    assert p.precio is None              # sin precio publicado: "Comprar WhatsApp"
    assert "AD1200" not in p.descripcion
    q = leer(suconel, "suconel_ut33c.html", "https://suconel.com/productos/multimetro-de-mano-uni-trend-ut33c")
    assert q.sku == "UT33C+"
    assert q.precio == 61980 and q.iva_incluido is False
    assert q.descripcion.startswith("El Multímetro de Mano Uni-Trend UT33C+")
    assert "UT33C+" in q.specs["modelos"]


def test_xl6009_es_el_mismo_que_tar_xl6009():
    from coincidencia import coincidencia_fuerte
    ref = leer(suconel, "suconel_xl6009.html", U_XL6009)
    c = leer(didacticas, "didacticas_tar_xl6009.html", U_TAR)
    assert c.specs["corriente_a"] == 3          # corriente de SALIDA, no la de entrada (4 A)
    ps, motivos, conflicto = puntaje_specs(ref.specs, c.specs)
    assert not conflicto and "mismo chip XL6009" in motivos
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, c.nombre, c.descripcion)
    assert combinar(ps, pd, None, conflicto, coincidencia_fuerte(ref.specs, c.specs, ps))[1] == "mismo"
    # la versión con display tiene otras medidas: no es el mismo producto
    d = leer(didacticas, "didacticas_tar_xl6009_disp.html", U_TAR_D)
    ps, _, conflicto = puntaje_specs(ref.specs, d.specs)
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, d.nombre, d.descripcion)
    assert combinar(ps, pd, None, conflicto, coincidencia_fuerte(ref.specs, d.specs, ps))[1] != "mismo"


def test_ut33c_es_el_mismo_en_didacticas():
    from coincidencia import coincidencia_fuerte
    ref = leer(suconel, "suconel_ut33c.html", "https://suconel.com/productos/multimetro-de-mano-uni-trend-ut33c")
    c = leer(didacticas, "didacticas_ut33c.html", "https://www.didacticaselectronicas.com/shop/ut33c-multimetro-digital-ut-33c-unit-11599")
    assert c.sku == "UT33C+" and c.precio == 63879.20
    ps, motivos, conflicto = puntaje_specs(ref.specs, c.specs)
    assert "mismo modelo UT33C+" in motivos and not conflicto
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, c.nombre, c.descripcion)
    assert combinar(ps, pd, None, conflicto, coincidencia_fuerte(ref.specs, c.specs, ps))[1] == "mismo"


def test_terminos_de_busqueda():
    from comparar import terminos_busqueda
    ref = leer(suconel, "suconel_ut33c.html", "https://suconel.com/productos/multimetro-de-mano-uni-trend-ut33c")
    t = terminos_busqueda(ref, {})
    assert t[0] == "UT33C+" and "UT33C" in t and "UT363BT" not in t


def test_sku_desde_la_url():
    p = leer(suconel, "suconel_ar3.html",
             "https://suconel.com/productos/placa-arduino-uno-r3-para-control-electronico-basico-con-chip-ch340-y-cable-usb-ar3")
    assert p.sku == "AR3"


def test_variantes_y_referencia():
    from coincidencia import coincidencia_fuerte, diferencias_variante, misma_referencia
    assert misma_referencia("HC06", "BT-HC-06") and misma_referencia("XL6009", "TAR-XL6009")
    assert not misma_referencia("AR3", "D-ESP32-30PBAT-C") and not misma_referencia("DS18B20", "DFR0198")
    suc = "Sensor De Temperatura DS18B20 Con Sonda Impermeable De 1 Metro Para Aplicaciones Técnicas DS18B20"
    assert "sonda" in diferencias_variante(suc, "Módulo sensor de temperatura DS18B20")
    assert diferencias_variante(suc, "Sensor de temperatura a prueba de agua DS18B20 - Cable 4MTS") == ["cable 1 m vs 4 m"]
    assert diferencias_variante(suc, "Sensor de temperatura a prueba de agua DS18B20") == []
    assert "display" in diferencias_variante("Módulo XL6009", "Conversor DC/DC Elevador. 35V 3A. Con display")
    assert diferencias_variante("Módulo Xl6009 Boost De 4A XL6009", "Conversor DC/DC Elevador. 35V 3A") == []
    # misma referencia + sin diferencias de variante => mismo producto
    assert coincidencia_fuerte({"modelos": ["HC06"]}, {"modelos": ["HC06"]}, 100, "HC06", "BT-HC-06",
                               "Módulo Bluetooth HC-06", "Módulo Bluetooth HC06, V 2.3_1E")
    # el mismo chip (CH340) en el nombre NO basta
    assert not coincidencia_fuerte({"modelos": ["CH340"]}, {"modelos": ["CH340"]}, 100, "AR3", "D-ESP32-30PBAT-C",
                                   "Placa Arduino Uno R3 Con Chip CH340", "Módulo WiFi/Bluetooth ESP-32. Con CH340")


def test_priorizar_resultados():
    from comparar import priorizar
    from tiendas.base import Enlace
    ref = leer(suconel, "suconel_ut33c.html", "https://suconel.com/productos/multimetro-de-mano-uni-trend-ut33c")
    a = Enlace("https://x/shop/anemometro-1", "Anemómetro mini digital UT363BT $ 138.242")
    b = Enlace("https://x/shop/ut33c-multimetro-digital-ut-33c-unit-11599", "[UT33C+] Multímetro digital UT-33C+ UNIT $ 63.879")
    assert priorizar(ref, [a, b]) == [b]


def test_limite_diario_se_informa(monkeypatch):
    import comparar
    from tiendas import didacticas
    from tiendas.base import LimiteDiario

    class C:
        via_firecrawl = set()

        def html(self, u):
            if "suconel" in u:
                return (PAG / "suconel_ut33c.html").read_text(encoding="utf-8")
            raise LimiteDiario("Se alcanzó el límite diario de páginas de Firecrawl (FIRECRAWL_MAX_DIA)")

        def bytes(self, u):
            raise RuntimeError

    monkeypatch.setattr(didacticas, "buscar", lambda c, t, maximo=8: c.html("https://didacticas/x"))
    r = comparar.procesar(C(), {"id": "x", "suconel": "https://suconel.com/productos/multimetro-de-mano-uni-trend-ut33c",
                                "competidores": {"didacticas": {}}}, 0.19, {})
    assert r["competidores"][0]["estado"] == "limite"
