"""Utilidades comunes a todos los conectores de tiendas."""
from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; ComparadorPreciosSuconel/1.0)"
PAUSA_SEG = 2.0          # pausa entre peticiones a la misma tienda


class Bloqueado(Exception):
    """La tienda rechazó la petición (403, 429, captcha…). No se intenta saltar el bloqueo."""


@dataclass
class Producto:
    tienda: str
    url: str
    nombre: str = ""
    sku: str = ""
    precio: float | None = None           # tal como lo publica la tienda
    iva_incluido: bool | None = None      # None = la página no lo aclara
    descripcion: str = ""
    imagen: str = ""
    specs: dict = field(default_factory=dict)

    def precio_con_iva(self, iva: float = 0.19) -> float | None:
        if self.precio is None:
            return None
        return round(self.precio * (1 + iva), 2) if self.iva_incluido is False else self.precio


class Cliente:
    """Cliente HTTP educado: respeta robots.txt y hace pausas entre peticiones."""

    def __init__(self):
        self.http = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "es-CO,es;q=0.9"},
                                 timeout=25, follow_redirects=True)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._ultimo: dict[str, float] = {}

    def _permitido(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.http.get(f"{urlparse(url).scheme}://{host}/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                self._robots[host] = rp
            except httpx.HTTPError:
                self._robots[host] = None
        rp = self._robots[host]
        return rp is None or rp.can_fetch(UA, url)

    def _esperar(self, url: str):
        host = urlparse(url).netloc
        falta = PAUSA_SEG - (time.monotonic() - self._ultimo.get(host, 0))
        if falta > 0:
            time.sleep(falta)
        self._ultimo[host] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        if not self._permitido(url):
            raise Bloqueado(f"robots.txt no permite {url}")
        self._esperar(url)
        r = self.http.get(url)
        if r.status_code in (401, 403, 429, 503):
            raise Bloqueado(f"{urlparse(url).netloc} respondió {r.status_code}")
        r.raise_for_status()
        return r

    def html(self, url: str) -> str:
        return self.get(url).text

    def bytes(self, url: str) -> bytes:
        return self.get(url).content


# ---------- ayudas de extracción ----------

def sopa(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def texto(s: BeautifulSoup) -> str:
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    lineas = (l.strip() for l in s.get_text("\n").splitlines())
    return "\n".join(l for l in lineas if l)


def meta(s: BeautifulSoup, *nombres: str) -> str:
    for n in nombres:
        t = s.find("meta", attrs={"property": n}) or s.find("meta", attrs={"name": n}) or s.find("meta", attrs={"itemprop": n})
        if t and t.get("content"):
            return t["content"].strip()
    return ""


def jsonld_producto(s: BeautifulSoup) -> dict:
    for t in s.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(t.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for d in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(d, dict) and d.get("@type") == "Product":
                return d
    return {}


def precio_cop(txt: str) -> float | None:
    """'$ 3.135' -> 3135 · '$ 5.654,88' -> 5654.88 · '$ 6,900' -> 6900 · '3135.5' -> 3135.5"""
    t = re.sub(r"[^\d,.]", "", txt or "")
    if not t:
        return None
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        mil = "." if dec == "," else ","
        t = t.replace(mil, "").replace(dec, ".")
    else:
        sep = "," if "," in t else "." if "." in t else ""
        if sep:
            partes = t.split(sep)
            if all(len(p) == 3 for p in partes[1:]):   # separador de miles
                t = "".join(partes)
            else:
                t = t.replace(sep, ".")
    try:
        return float(t)
    except ValueError:
        return None


def absoluta(base: str, src: str) -> str:
    return urljoin(base, src) if src else ""
