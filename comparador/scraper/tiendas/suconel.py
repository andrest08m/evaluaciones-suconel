"""Conector de suconel.com (tienda de referencia)."""
from __future__ import annotations

import re

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
    t = texto(s)

    # El primer "SKU:" es el del producto; los siguientes son de "Productos relacionados".
    m_sku = re.search(r"SKU:\s*([A-Za-z0-9._\-/]+)", t)
    m_precio = re.search(r"Precio\s*\$\s*([\d.,]+)\s*(\\?\+\s*IVA)?", t)
    precio = precio_cop(m_precio.group(1)) if m_precio else precio_cop(str(ld.get("offers", {}).get("price", "")))

    # Descripción: del título hasta "Productos relacionados" (sin el precio ni la lista de categorías).
    fin = t.find("Productos relacionados")
    fin = fin if fin > 0 else len(t)
    corte = t.find("Precio") if 0 < t.find("Precio") < fin else fin
    ini = t.rfind(nombre, 0, corte) + len(nombre) if nombre and t.rfind(nombre, 0, corte) >= 0 else 0
    desc = t[ini:fin]
    desc = re.sub(r"Categorías:.*?(?=\n[^\n]{40,}|\Z)", "\n", desc, flags=re.S)
    desc = re.sub(r"Precio\s*\$[^\n]*|Precio\n|\$\s*[\d.,]+\s*\\?\+?\s*IVA|SKU:[^\n]*|Te gustó este producto[^\n]*", "\n", desc)

    return Producto(
        tienda=TIENDA, url=url, nombre=nombre,
        sku=m_sku.group(1) if m_sku else ld.get("sku", ""),
        precio=precio,
        iva_incluido=False if (m_precio and m_precio.group(2)) else None,
        descripcion=_limpiar(desc),
        imagen=absoluta(url, imagen),
    )


def _imagen(ld: dict) -> str:
    img = ld.get("image", "")
    return img[0] if isinstance(img, list) and img else img if isinstance(img, str) else ""


def _limpiar(t: str) -> str:
    """Conserva los saltos de línea (separan las características) y quita espacios sobrantes."""
    lineas = (re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.splitlines())
    return "\n".join(l for l in lineas if l)
