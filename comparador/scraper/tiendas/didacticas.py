"""Conector de didacticaselectronicas.com (tienda en Odoo)."""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from .base import Cliente, Enlace, Producto, absoluta, jsonld_producto, meta, precio_cop, sopa, texto

TIENDA = "Didácticas Electrónicas"
BASE = "https://www.didacticaselectronicas.com"
RE_PRODUCTO = re.compile(r"^/shop/(?!category/|cart|checkout|wishlist|products/)[a-z0-9\-]+-\d+$")


def buscar(cli: Cliente, termino: str, maximo: int = 8) -> list[Enlace]:
    """Usa el buscador de la tienda (/shop?search=…) y devuelve URLs de producto."""
    html = cli.html(f"{BASE}/shop?search={quote_plus(termino)}")
    return urls_de_busqueda(html, maximo)


def urls_de_busqueda(html: str, maximo: int = 8) -> list[Enlace]:
    """URLs de producto de la página de resultados, con el texto de su tarjeta (nombre, [referencia], precio)."""
    urls: list[Enlace] = []
    vistos: dict[str, Enlace] = {}
    for a in sopa(html).find_all("a", href=True):
        ruta = a["href"].split("?")[0].split("#")[0]
        if ruta.startswith(BASE):
            ruta = ruta[len(BASE):]
        if not RE_PRODUCTO.match(ruta):
            continue
        tarjeta = a.find_parent(class_=re.compile(r"oe_product|o_wsale_product|product_card|card")) or a
        txt = " ".join(filter(None, [tarjeta.get_text(" ", strip=True), a.get("title", ""), a.get("aria-label", "")]))
        u = BASE + ruta
        if u in vistos:
            vistos[u].texto += " " + txt
            continue
        if len(urls) >= maximo:
            continue
        vistos[u] = Enlace(u, txt)
        urls.append(vistos[u])
    return urls


def leer(html: str, url: str) -> Producto:
    s = sopa(html)
    ld = jsonld_producto(s)
    titulo = meta(s, "og:title") or (s.title.get_text(strip=True) if s.title else "")
    h1 = s.find("h1")
    nombre = (h1.get_text(" ", strip=True) if h1 else "") or ld.get("name") or titulo
    nombre = re.sub(r"\s*\|\s*Didácticas.*$", "", re.sub(r"^\[[^\]]+\]\s*", "", nombre))

    # Odoo muestra la referencia interna entre corchetes: "[LM2596-V-5A] Conversor…"
    m_ref = re.search(r"\[([^\]]+)\]", titulo) or re.search(r"\[([^\]]+)\]", s.get_text(" "))

    precio = None
    tag = s.find(attrs={"itemprop": "price"})
    if tag:
        precio = precio_cop(tag.get("content") or tag.get_text())
    if precio is None:
        val = s.select_one(".oe_price .oe_currency_value, .oe_currency_value")
        precio = precio_cop(val.get_text()) if val else None
    t = texto(s)
    if precio is None:
        m = re.search(r"Precio:?\s*\$\s*([\d.,]+)", t)
        precio = precio_cop(m.group(1)) if m else None

    # Descripción completa (pestaña "Descripción"/"Especificaciones") y, si existe, el resumen corto.
    partes = [c.get_text("\n", strip=True) for c in
              (s.select_one("[itemprop=description]"), s.select_one("#product_full_description")) if c]
    if not partes and (c := s.select_one("#product_details")):
        partes = [c.get_text("\n", strip=True)]
    desc = "\n".join(partes)
    if not desc:
        ini = t.find(nombre, t.find(nombre) + 1) if nombre else 0
        fin = t.find("Suscríbete")
        desc = t[max(ini, 0):fin if fin > 0 else None]

    return Producto(
        tienda=TIENDA, url=url, nombre=nombre,
        sku=m_ref.group(1) if m_ref else ld.get("sku", ""),
        precio=precio,
        iva_incluido=None,   # la tarifa pública no indica si incluye IVA: se configura en productos.json
        descripcion=_limpiar(desc),
        imagen=absoluta(url, meta(s, "og:image") or (s.select_one("img[itemprop=image]") or {}).get("src", "")),
    )


def _limpiar(t: str) -> str:
    """Conserva los saltos de línea (separan las características) y quita espacios sobrantes."""
    lineas = (re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.splitlines())
    return "\n".join(l for l in lineas if l)
