"""Llena comparador/productos.json con los productos de suconel.com de una o varias categorías.

Uso (desde la raíz del repositorio):
    python comparador/scraper/catalogo.py --categorias modulos,fuentes-de-alimentacion --maximo 60 \
        --competidores didacticas,electronilab,mercadolibre
    python comparador/scraper/catalogo.py --categorias todas      # todo el catálogo, vía sitemap.xml

Respeta robots.txt y hace pausas (usa Cliente). Conserva "iva" y "_ejemplo" del archivo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from tiendas.base import Bloqueado, Cliente, sopa

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "productos.json"
BASE = "https://suconel.com"
CATEGORIAS_DEFECTO = ["modulos", "fuentes-de-alimentacion", "multimetros-digitales"]
COMPETIDORES_DEFECTO = ["didacticas"]
MAX_PAGINAS = 30
MAX_SITEMAPS = 20
TEXTOS_SIGUIENTE = {"next", "siguiente", "›", "»", ">", "next »", "siguiente »", "next ›"}


def _limpia(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", ""))


def urls_de_categoria(html: str, base_url: str) -> list[str]:
    """URLs de producto (cualquier <a> con /productos/ en el href), absolutas y sin duplicados."""
    vistas: dict[str, None] = {}
    for a in sopa(html).find_all("a", href=True):
        href = a["href"].strip()
        if "/productos/" not in href:
            continue
        url = _limpia(urljoin(base_url, href))
        if urlparse(url).path.strip("/").count("/") >= 1 and url.rstrip("/").split("/productos/")[-1]:
            vistas.setdefault(url, None)
    return list(vistas)


def _numero_pagina(url: str) -> int:
    try:
        return int(parse_qs(urlparse(url).query).get("page", ["1"])[0])
    except ValueError:
        return 1


def siguiente_pagina(html: str, url_actual: str) -> str | None:
    """Enlace a la página siguiente: rel="next", texto Next/Siguiente/›, o ?page=N+1."""
    s = sopa(html)
    enlaces = s.find_all("a", href=True)
    for a in enlaces:                                       # 1) rel="next"
        if "next" in [r.lower() for r in (a.get("rel") or [])]:
            return urljoin(url_actual, a["href"])
    for l in s.find_all("link", href=True):
        if "next" in [r.lower() for r in (l.get("rel") or [])]:
            return urljoin(url_actual, l["href"])
    actual = urlparse(url_actual)
    for a in enlaces:                                       # 2) texto "Next" / "Siguiente" / ›
        href = a["href"].strip()
        if a.get_text(" ", strip=True).lower() in TEXTOS_SIGUIENTE and href and not href.startswith(("#", "javascript")):
            destino = urljoin(url_actual, href)
            if destino != url_actual:
                return destino
    objetivo = _numero_pagina(url_actual) + 1               # 3) ?page=N+1
    for a in enlaces:
        destino = urlparse(urljoin(url_actual, a["href"]))
        if (destino.netloc, destino.path) == (actual.netloc, actual.path) and _numero_pagina(destino.geturl()) == objetivo \
                and "page" in parse_qs(destino.query):
            return destino.geturl()
    return None


def _locs(xml: str) -> list[str]:
    return [u.strip() for u in re.findall(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", xml, flags=re.S | re.I)]


def urls_de_sitemap(xml: str) -> list[str]:
    """<loc> que apuntan a productos (sin duplicados, en orden)."""
    return list(dict.fromkeys(_limpia(u) for u in _locs(xml) if "/productos/" in u))


def sitemaps_anidados(xml: str) -> list[str]:
    """<loc> de un índice de sitemaps (los que terminan en .xml o .xml.gz)."""
    return [u for u in _locs(xml) if re.search(r"\.xml(\.gz)?(\?.*)?$", u, re.I)]


def id_de_url(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1][:120]


def armar_entradas(urls: list[str], categoria: str, competidores: list[str]) -> list[dict]:
    return [{"id": id_de_url(u), "suconel": u, "categoria": categoria,
             "competidores": {c: {"maximo": 5} for c in competidores}} for u in urls]


def fusionar(actuales: list[dict], nuevas: list[dict]) -> list[dict]:
    """Conserva las entradas existentes (mismo id); solo les agrega 'categoria' si falta."""
    por_id = {e.get("id"): e for e in actuales}
    salida = list(actuales)
    for e in nuevas:
        previa = por_id.get(e["id"])
        if previa is None:
            por_id[e["id"]] = e
            salida.append(e)
        elif "categoria" not in previa:
            previa["categoria"] = e["categoria"]
    return salida


# ---------- lectura del sitio ----------

def urls_por_sitemap(cli: Cliente, base: str = BASE) -> list[str]:
    """Productos del sitemap (y sitemaps anidados). Lista vacía si no existe o no sirve."""
    try:
        pendientes, vistos, urls = [f"{base}/sitemap.xml"], set(), []
        while pendientes and len(vistos) < MAX_SITEMAPS:
            sm = pendientes.pop(0)
            if sm in vistos:
                continue
            vistos.add(sm)
            xml = cli.get(sm).text
            urls += urls_de_sitemap(xml)
            pendientes += sitemaps_anidados(xml)
        return list(dict.fromkeys(urls))
    except Exception as e:                                  # sin sitemap: se usan las páginas de categoría
        print(f"  sitemap no disponible ({type(e).__name__}: {e})", file=sys.stderr)
        return []


def urls_por_categoria(cli: Cliente, slug: str, maximo: int, base: str = BASE) -> list[str]:
    """Recorre las páginas de la categoría hasta `maximo` productos, sin páginas nuevas o 30 páginas."""
    url, vistas, urls = f"{base}/categorias/{slug}", set(), {}
    for n in range(1, MAX_PAGINAS + 1):
        if url in vistas:
            break
        vistas.add(url)
        html = cli.html(url)
        nuevas = [u for u in urls_de_categoria(html, url) if u not in urls]
        if not nuevas:
            break
        urls.update(dict.fromkeys(nuevas))
        if maximo and len(urls) >= maximo:
            break
        url = siguiente_pagina(html, url) or f"{base}/categorias/{slug}?page={n + 1}"
    return list(urls)[:maximo] if maximo else list(urls)


def cargar(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"iva": 0.19, "productos": []}


def recolectar(cli: Cliente, categorias: list[str], maximo: int, competidores: list[str]) -> list[dict]:
    entradas = []
    if categorias == ["todas"]:
        urls = urls_por_sitemap(cli)
        if not urls:
            sys.exit("No se pudo leer sitemap.xml: indica categorías concretas.")
        print(f"sitemap: {len(urls)} productos")
        return armar_entradas(urls[:maximo] if maximo else urls, "todas", competidores)
    for slug in categorias:
        try:
            urls = urls_por_categoria(cli, slug, maximo)
        except Bloqueado as e:
            print(f"  {slug}: bloqueado ({e})", file=sys.stderr)
            continue
        print(f"{slug}: {len(urls)} productos")
        entradas += armar_entradas(urls, slug, competidores)
    return entradas


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Llena productos.json con productos de suconel.com")
    ap.add_argument("--categorias", default=",".join(CATEGORIAS_DEFECTO),
                    help="slugs separados por coma, o 'todas' para usar sitemap.xml")
    ap.add_argument("--maximo", type=int, default=60, help="máximo de productos por categoría (0 = sin límite)")
    ap.add_argument("--competidores", default=",".join(COMPETIDORES_DEFECTO))
    ap.add_argument("--reemplazar", action="store_true", help="empezar de cero (descarta los productos actuales)")
    ap.add_argument("--salida", default=str(CATALOGO), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    categorias = [c.strip() for c in a.categorias.split(",") if c.strip()]
    competidores = [c.strip() for c in a.competidores.split(",") if c.strip()]
    ruta = Path(a.salida)

    datos = cargar(ruta)
    nuevas = recolectar(Cliente(), categorias, a.maximo, competidores)
    base = [] if a.reemplazar else datos.get("productos", [])
    datos["productos"] = fusionar(base, nuevas)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(datos['productos'])} productos en {ruta}")


if __name__ == "__main__":
    main()
