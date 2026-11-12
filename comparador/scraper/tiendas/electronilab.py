"""Conector de electronilab.co (WooCommerce, Bogotá). Primero la API pública de la tienda, si no el HTML."""
from __future__ import annotations

import re
from urllib.parse import quote_plus

import httpx

from .base import Bloqueado, Cliente, Enlace, Producto, absoluta, jsonld_producto, meta, precio_cop, sopa, texto

TIENDA = "Electronilab"
BASE = "https://electronilab.co"


def buscar(cli: Cliente, termino: str, maximo: int = 8) -> list[Enlace]:
    try:
        r = cli.get(f"{BASE}/wp-json/wc/store/v1/products?search={quote_plus(termino)}&per_page={maximo}")
        enlaces = enlaces_de_api(r.json(), maximo)
        if enlaces:
            return enlaces
    except Bloqueado:
        raise
    except (httpx.HTTPError, ValueError):
        pass                                   # sin API o respuesta que no es JSON: búsqueda HTML
    html = cli.html(f"{BASE}/?s={quote_plus(termino)}&post_type=product")
    return urls_de_busqueda(html, maximo)


def enlaces_de_api(datos, maximo: int = 8) -> list[Enlace]:
    out: list[Enlace] = []
    if not isinstance(datos, list):
        return out
    for it in datos:
        if not isinstance(it, dict) or not it.get("permalink"):
            continue
        try:
            precio = float((it.get("prices") or {}).get("price")) / 100
            p = f"${precio:,.0f}"
        except (TypeError, ValueError):
            p = ""
        out.append(Enlace(it["permalink"], " ".join(filter(None, [it.get("name", ""), it.get("sku", ""), p]))))
        if len(out) >= maximo:
            break
    return out


def urls_de_busqueda(html: str, maximo: int = 8) -> list[Enlace]:
    vistos: dict[str, Enlace] = {}
    for a in sopa(html).find_all("a", href=True):
        h = a["href"].split("?")[0].split("#")[0]
        if "/tienda/" not in h or h.rstrip("/").endswith("/tienda"):
            continue
        u = absoluta(BASE, h)
        tarjeta = a.find_parent(class_=re.compile(r"product|card")) or a
        txt = " ".join(filter(None, [tarjeta.get_text(" ", strip=True), a.get("title", ""), a.get("aria-label", "")]))
        if u in vistos:
            vistos[u].texto += " " + txt
        elif len(vistos) < maximo:
            vistos[u] = Enlace(u, txt)
    return list(vistos.values())


def leer(html: str, url: str) -> Producto:
    s = sopa(html)
    ld = jsonld_producto(s)
    h1 = s.find("h1")
    nombre = (h1.get_text(" ", strip=True) if h1 else "") or ld.get("name") or meta(s, "og:title")
    t = texto(sopa(html))

    sku = str(ld.get("sku") or "")
    if not sku:
        m = re.search(r"SKU:\s*(\S+)", t)
        sku = m.group(1) if m else ""

    precio = None
    ofertas = ld.get("offers")
    if isinstance(ofertas, list):
        ofertas = ofertas[0] if ofertas else {}
    if isinstance(ofertas, dict):
        precio = precio_cop(str(ofertas.get("price") or "")) or precio_cop(str((ofertas.get("priceSpecification") or {}).get("price") or ""))
    if precio is None:
        m = re.search(r"\$\s*([\d.,]+)\s*COP", t) or re.search(r"\$\s*([\d.,]+)", t)
        precio = precio_cop(m.group(1)) if m else None

    c = s.select_one("#tab-description, .woocommerce-Tabs-panel--description, [itemprop=description]")
    desc = c.get_text("\n", strip=True) if c else ""
    if not desc:
        desc = str(ld.get("description") or "")
    if not desc:
        ini = t.find("Descripción", t.find("Descripción") + 1) if "Descripción" in t else 0
        fin = t.find("Frecuentemente comprados")
        desc = t[max(ini, 0):fin if fin > 0 else None]

    img = meta(s, "og:image") or ld.get("image") or ""
    if isinstance(img, list):
        img = img[0] if img else ""
    return Producto(tienda=TIENDA, url=url, nombre=nombre, sku=sku, precio=precio,
                    iva_incluido=True, descripcion=_limpiar(desc), imagen=absoluta(url, str(img)))


def _limpiar(t: str) -> str:
    lineas = (re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.splitlines())
    return "\n".join(l for l in lineas if l)
