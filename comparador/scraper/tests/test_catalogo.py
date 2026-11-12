"""Pruebas de catalogo.py con páginas de ejemplo (sin red)."""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

import catalogo  # noqa: E402

PAG = AQUI / "paginas"
CAT = "https://suconel.com/categorias/modulos"
LM = "https://suconel.com/productos/modulo-regulador-dc-dc-ajustable-lm-2596"


def html():
    return (PAG / "suconel_categoria_modulos.html").read_text(encoding="utf-8")


def test_urls_de_categoria():
    urls = catalogo.urls_de_categoria(html(), CAT)
    assert LM in urls
    assert len(urls) == len(set(urls)) == 6          # 5 de la cuadrícula + 1 destacado; sin duplicados
    assert all("/productos/" in u for u in urls)
    assert not any("/categorias/" in u for u in urls)


def test_urls_relativas():
    assert catalogo.urls_de_categoria('<a href="/productos/abc?x=1#y">a</a>', CAT) == ["https://suconel.com/productos/abc"]


def test_siguiente_pagina():
    assert catalogo.siguiente_pagina(html(), CAT) == CAT + "?page=2"
    assert catalogo.siguiente_pagina('<a rel="next" href="/c?p=7">x</a>', CAT) == "https://suconel.com/c?p=7"
    assert catalogo.siguiente_pagina('<a href="/x">Siguiente</a>', CAT) == "https://suconel.com/x"
    assert catalogo.siguiente_pagina('<a href="?page=3">3</a><a href="?page=2">2</a>', CAT) == CAT + "?page=2"
    assert catalogo.siguiente_pagina('<a href="?page=2">2</a>', CAT + "?page=2") is None
    assert catalogo.siguiente_pagina("<p>nada</p>", CAT) is None


def test_sitemap():
    xml = (PAG / "suconel_sitemap.xml").read_text(encoding="utf-8")
    urls = catalogo.urls_de_sitemap(xml)
    assert urls == [LM, "https://suconel.com/productos/modulo-puente-h-l298n",
                    "https://suconel.com/productos/multimetro-digital-trms-uni-trend-ut139c"]
    indice = "<sitemapindex><sitemap><loc>https://suconel.com/sm-productos.xml</loc></sitemap></sitemapindex>"
    assert catalogo.sitemaps_anidados(indice) == ["https://suconel.com/sm-productos.xml"]
    assert catalogo.urls_de_sitemap(indice) == []


def test_armar_entradas():
    e = catalogo.armar_entradas([LM], "modulos", ["didacticas", "electronilab"])
    assert e == [{"id": "modulo-regulador-dc-dc-ajustable-lm-2596", "suconel": LM, "categoria": "modulos",
                  "competidores": {"didacticas": {"maximo": 5}, "electronilab": {"maximo": 5}}}]
    assert len(catalogo.id_de_url("https://suconel.com/productos/" + "a" * 300)) == 120


def test_fusionar_conserva_y_no_duplica():
    previa = {"id": "modulo-regulador-dc-dc-ajustable-lm-2596", "suconel": LM, "competidores": {"didacticas": {"maximo": 8}}}
    nuevas = catalogo.armar_entradas([LM, "https://suconel.com/productos/otro"], "modulos", ["didacticas"])
    r = catalogo.fusionar([previa], nuevas)
    assert [x["id"] for x in r] == ["modulo-regulador-dc-dc-ajustable-lm-2596", "otro"]
    assert r[0]["competidores"]["didacticas"]["maximo"] == 8 and r[0]["categoria"] == "modulos"


class Falso:
    """Cliente falso: página 1 sin enlace 'Next' para probar el recurso ?page=N."""
    def __init__(self):
        self.pedidas = []

    def html(self, url):
        self.pedidas.append(url)
        n = {CAT: 1, CAT + "?page=2": 2}.get(url, 3)
        return "".join(f'<a href="/productos/p{n}-{i}">x</a>' for i in range(2)) if n < 3 else "<p>fin</p>"


def test_recorrido_sin_paginacion_detectable():
    cli = Falso()
    urls = catalogo.urls_por_categoria(cli, "modulos", 0)
    assert len(urls) == 4 and cli.pedidas == [CAT, CAT + "?page=2", CAT + "?page=3"]
    assert len(catalogo.urls_por_categoria(Falso(), "modulos", 3)) == 3


def test_main_escribe_json(tmp_path, monkeypatch):
    ruta = tmp_path / "productos.json"
    ruta.write_text(json.dumps({"iva": 0.16, "productos": [], "_ejemplo": {"id": "x"}}), encoding="utf-8")
    monkeypatch.setattr(catalogo, "Cliente", lambda: Falso())
    catalogo.main(["--categorias", "modulos", "--competidores", "didacticas,electronilab", "--salida", str(ruta)])
    d = json.loads(ruta.read_text(encoding="utf-8"))
    assert d["iva"] == 0.16 and d["_ejemplo"] == {"id": "x"} and len(d["productos"]) == 4
    assert d["productos"][0]["categoria"] == "modulos"
    catalogo.main(["--categorias", "modulos", "--salida", str(ruta)])       # idempotente
    assert len(json.loads(ruta.read_text(encoding="utf-8"))["productos"]) == 4
    catalogo.main(["--categorias", "modulos", "--maximo", "1", "--reemplazar", "--salida", str(ruta)])
    assert len(json.loads(ruta.read_text(encoding="utf-8"))["productos"]) == 1
