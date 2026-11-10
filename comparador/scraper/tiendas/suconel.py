"""Conector de suconel.com (tienda de referencia)."""
from __future__ import annotations

import re
from urllib.parse import unquote

from .base import Producto, absoluta, jsonld_producto, meta, precio_cop, sopa, texto

TIENDA = "Suconel"


def leer(html: str, url: str) -> Producto:
    s = sopa(html)
    ld = jsonld_producto(s)
    h1 = s.find("h1")
    nombre = (h1.get_text(" ", strip=True) if h1 else "") or ld.get("name") or re.sub(r"^Suconel\s*\|\s*", "", meta(s, "og:title"))
    imagen = meta(s, "og:image") or _imagen(ld)
    if not imagen:
        img = s.find("img", alt=lambda a: a and nombre and nombre.lower() in a.lower())
        imagen = img.get("src", "") if img else ""

    # Solo se mira el bloque del producto: desde el título (h1) hasta "Productos relacionados".
    # Así nunca se toma el SKU ni el precio de un producto relacionado.
    principal = _bloque_principal(h1) if h1 else texto(s)

    m_precio = re.search(r"Precio\s*\$\s*([\d.,]+)\s*(\\?\+\s*IVA)?", principal)
    precio = precio_cop(m_precio.group(1)) if m_precio else precio_cop(str((ld.get("offers") or {}).get("price", "")))

    desc = re.sub(r"Categorías:.*?(?=\n[^\n]{40,}|\Z)", "\n", principal, flags=re.S)
    desc = re.sub(r"Marca:[^\n]*|Precio\s*\$[^\n]*|Precio\n|\$\s*[\d.,]+\s*\\?\+?\s*IVA|SKU:?[^\n]*\n?[^\n]*|"
                  r"Te gustó este producto[^\n]*|Comprar WhatsApp|Añadir al carrito", "\n", desc)

    return Producto(
        tienda=TIENDA, url=url, nombre=nombre,
        sku=_sku(principal, s, nombre, url) or ld.get("sku", ""),
        precio=precio,
        iva_incluido=False if (m_precio and m_precio.group(2)) else None,
        descripcion=_limpiar(desc),
        imagen=absoluta(url, imagen),
    )


def _bloque_principal(h1) -> str:
    partes = []
    for st in h1.find_all_next(string=True):
        if st.parent and st.parent.name in ("script", "style", "noscript"):
            continue
        if h1 in st.parents:          # el propio título
            continue
        x = st.strip()
        if not x:
            continue
        if x.startswith("Productos relacionados"):
            break
        partes.append(x)
    return "\n".join(partes)


def _sku(principal: str, s, nombre: str, url: str = "") -> str:
    # 1) "SKU: XL6009" dentro del bloque del producto (el valor puede venir en otra etiqueta)
    # (los SKU de Suconel van en mayúsculas: XL6009, UT33C+, AR3; así no se toma la palabra siguiente, p. ej. «Voltaje»)
    m = re.search(r"\bSKU:?[ \t]*\n?[ \t]*([A-Z0-9][A-Z0-9._\-/+]*)(?=\s|$)", principal)
    if m:
        return m.group(1)
    # 2) El enlace "Comprar WhatsApp" del producto lleva "*SKU:* XL6009"
    for a in s.find_all("a", href=re.compile(r"wa\.me|whatsapp", re.I)):
        txt = unquote(a["href"])
        m = re.search(r"\*SKU:\*\s*([^\s*]+)", txt)
        if m and nombre[:25].lower() in txt.lower():
            return m.group(1)
    # 3) La URL termina con el SKU: …-uni-trend-ut33c, …-cable-usb-ar3 → el token del nombre que coincide
    cola = re.sub(r"[^a-z0-9]", "", url.rstrip("/").rsplit("/", 1)[-1].lower())
    for tok in reversed(nombre.split()):
        t = re.sub(r"[^a-z0-9]", "", tok.lower())
        if len(t) >= 2 and re.search(r"\d", t) and cola.endswith(t):
            return tok
    # 4) El modelo suele ir al final del nombre: "… Uni-Trend UT33C+", "… Boost De 4A XL6009"
    for tok in reversed(nombre.split()):
        if re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok) and len(tok) >= 4 and not re.fullmatch(r"\d+(?:[.,]\d+)?[a-zA-Z]{1,3}", tok):
            return tok
    return ""


def _imagen(ld: dict) -> str:
    img = ld.get("image", "")
    return img[0] if isinstance(img, list) and img else img if isinstance(img, str) else ""


def _limpiar(t: str) -> str:
    """Conserva los saltos de línea (separan las características) y quita espacios sobrantes."""
    lineas = (re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.splitlines())
    return "\n".join(l for l in lineas if l)
