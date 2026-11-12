"""Conector de Mercado Libre Colombia mediante su API pública (sin clave)."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote_plus

from .base import Cliente, Enlace, Producto

TIENDA = "Mercado Libre"
BASE = "https://api.mercadolibre.com"

_items: dict[str, dict] = {}      # url -> item JSON de la búsqueda, para no volver a pedirlo


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def buscar(cli: Cliente, termino: str, maximo: int = 8) -> list[Enlace]:
    datos = cli.get(f"{BASE}/sites/MCO/search?q={quote_plus(termino)}&limit={maximo}").json()
    vistos, elegidos = set(), []
    for it in sorted(datos.get("results", []), key=lambda i: i.get("price") or 0):
        if it.get("condition") != "new" or not it.get("permalink"):
            continue
        k = _norm(it.get("title", ""))
        if k in vistos:
            continue
        vistos.add(k)
        elegidos.append(it)
    if len(_items) > 500:                # el servidor vive días: no dejar crecer el caché sin límite
        _items.clear()
    out = []
    for it in elegidos:
        _items[it["permalink"]] = it
        out.append(Enlace(it["permalink"], it.get("title", "")))
    return out


def leer_url(cli: Cliente, url: str) -> Producto:
    if url in _items:
        return desde_item(_items[url], url)
    m = re.search(r"MCO-?(\d+)", url)
    if not m:
        raise ValueError(f"No se encontró el ID MCO en {url}")
    return desde_item(cli.get(f"{BASE}/items/MCO{m.group(1)}").json(), url)


def leer(html: str, url: str) -> Producto:
    """Sin red si la URL salió de buscar(); si no, hay que usar leer_url (necesita el cliente)."""
    if url in _items:
        return desde_item(_items[url], url)
    raise LookupError("Mercado Libre: usa leer_url(cli, url) para URLs que no vienen de buscar()")


def desde_item(it: dict, url: str) -> Producto:
    attrs = it.get("attributes") or []
    sku = next((a.get("value_name") for k in ("MODEL", "PART_NUMBER") for a in attrs
                if a.get("id") == k and a.get("value_name")), "") or it.get("id", "")
    lineas = [it.get("title", "")]
    lineas += [f"{a['name']}: {a['value_name']}" for a in attrs if a.get("name") and a.get("value_name")]
    nick = (it.get("seller") or {}).get("nickname")
    if nick:
        lineas.append(f"Vendedor: {nick}")
    lineas.append("Usado" if it.get("condition") == "used" else "Nuevo")
    img = (it.get("thumbnail") or "").replace("-I.jpg", "-O.jpg")
    return Producto(tienda=TIENDA, url=url, nombre=it.get("title", ""), sku=sku,
                    precio=it.get("price"), iva_incluido=True,
                    descripcion="\n".join(lineas), imagen=img)
