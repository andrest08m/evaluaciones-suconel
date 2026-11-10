"""Comparador de precios Suconel vs. otras tiendas.

Uso (desde la raíz del repositorio):
    pip install -r comparador/scraper/requirements.txt
    python comparador/scraper/comparar.py

Lee comparador/productos.json y escribe comparador/data/precios.json,
que es lo que muestra la página comparador/index.html.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from coincidencia import coincidencia_fuerte, combinar, diferencias_variante, misma_referencia, extraer_specs, puntaje_descripcion, puntaje_foto, puntaje_specs
from tiendas import didacticas, suconel
from tiendas.base import Bloqueado, Cliente, LimiteDiario, Producto

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "productos.json"
SALIDA = RAIZ / "data" / "precios.json"

COMPETIDORES = {"didacticas": didacticas}


def a_dict(p: Producto, iva: float) -> dict:
    return {"tienda": p.tienda, "url": p.url, "nombre": p.nombre, "sku": p.sku, "precio": p.precio,
            "iva_incluido": p.iva_incluido, "precio_con_iva": p.precio_con_iva(iva),
            "imagen": p.imagen, "descripcion": p.descripcion[:600], "specs": p.specs}


def foto(cli: Cliente, url: str, cache: dict) -> bytes | None:
    if not url:
        return None
    if url not in cache:
        try:
            cache[url] = cli.bytes(url)
        except Exception:
            cache[url] = None
    return cache[url]


def evaluar(ref: Producto, cand: Producto, img_ref, img_cand, iva: float) -> dict:
    ps, motivos, conflicto = puntaje_specs(ref.specs, cand.specs)
    pd = puntaje_descripcion(ref.nombre, ref.descripcion, cand.nombre, cand.descripcion)
    pf = puntaje_foto(img_ref, img_cand)
    fuerte = coincidencia_fuerte(ref.specs, cand.specs, ps, ref.sku, cand.sku, ref.nombre, cand.nombre)
    total, veredicto = combinar(ps, pd, pf, conflicto, fuerte)
    variantes = diferencias_variante(ref.nombre, cand.nombre)
    if variantes:
        motivos = motivos + ["variante distinta: " + ", ".join(variantes)]
        if veredicto == "mismo":
            veredicto = "posible"
    if misma_referencia(ref.sku, cand.sku):
        motivos = [f"misma referencia {cand.sku}"] + motivos
    d = a_dict(cand, iva)
    pr, pc = ref.precio_con_iva(iva), cand.precio_con_iva(iva)
    d.update(puntajes={"specs": ps, "descripcion": pd, "foto": pf, "total": total},
             veredicto=veredicto, motivos=motivos,
             diferencia_pct=round((pc - pr) / pr * 100, 1) if pr and pc else None)
    return d


def terminos_busqueda(ref: Producto, conf: dict) -> list[str]:
    """Qué buscar en la otra tienda: SKU, chips y modelos del nombre (y su versión sin símbolos: UT33C+ → UT33C)."""
    base = conf.get("buscar") or [ref.sku, *ref.specs.get("chips", []), *ref.specs.get("modelos", [])[:2]]
    out = []
    for t in base:
        for v in (t, re.sub(r"[^A-Za-z0-9]", "", t or "")):
            if v and len(v) >= 3 and v.upper() not in (x.upper() for x in out):
                out.append(v)
    return out[:4]


def relevancia(ref: Producto, enlace) -> int:
    """2 = el resultado de búsqueda menciona la referencia o el modelo; 1 = un chip; 0 = nada."""
    txt = re.sub(r"[^A-Z0-9+]", "", (getattr(enlace, "texto", "") + " " + str(enlace)).upper())
    codigos = [re.sub(r"[^A-Z0-9+]", "", c.upper()) for c in [ref.sku, *ref.specs.get("modelos", [])] if c]
    if any(len(c) >= 3 and c.rstrip("+") in txt for c in codigos):
        return 2
    if any(c in txt for c in ref.specs.get("chips", [])):
        return 1
    return 0


def priorizar(ref: Producto, enlaces: list) -> list:
    """Ordena por relevancia y, si hay resultados que mencionan la referencia, descarta los que no
    (así no se gastan créditos abriendo productos que no tienen nada que ver)."""
    con = sorted(enlaces, key=lambda e: -relevancia(ref, e))
    if con and relevancia(ref, con[0]) > 0:
        con = [e for e in con if relevancia(ref, e) > 0]
    return con


def procesar(cli: Cliente, item: dict, iva: float, previo: dict) -> dict:
    cache_fotos: dict = {}
    ref = suconel.leer(cli.html(item["suconel"]), item["suconel"])
    ref.specs = extraer_specs(ref.nombre, ref.descripcion, ref.sku, ref.url)
    img_ref = foto(cli, ref.imagen, cache_fotos)
    print(f"· {ref.nombre} ({ref.sku}) ${ref.precio}  specs={ref.specs}")

    salida = {"id": item["id"], "referencia": a_dict(ref, iva), "competidores": []}
    for clave, conf in item.get("competidores", {}).items():
        mod = COMPETIDORES[clave]
        res = {"tienda": mod.TIENDA, "estado": "ok", "candidatos": []}
        try:
            # 1) URLs puestas a mano en productos.json  2) búsqueda por referencia, chip y palabras clave
            urls = list(conf.get("urls", []))
            encontrados = []
            for t in terminos_busqueda(ref, conf):
                for u in mod.buscar(cli, t):
                    if u not in urls and u not in encontrados:
                        encontrados.append(u)
                if sum(1 for u in encontrados if relevancia(ref, u) >= 2) >= 2:
                    break                      # ya hay resultados con la referencia: no gastar más búsquedas
            urls += priorizar(ref, encontrados)
            for u in urls[: conf.get("maximo", 6)]:
                try:
                    c = mod.leer(cli.html(u), u)
                except Bloqueado:
                    raise
                except Exception as e:
                    print(f"   ! {u}: {e}")
                    continue
                if conf.get("iva_incluido") is not None:
                    c.iva_incluido = conf["iva_incluido"]
                c.specs = extraer_specs(c.nombre, c.descripcion, c.sku, c.url)
                res["candidatos"].append(evaluar(ref, c, img_ref, foto(cli, c.imagen, cache_fotos), iva))
        except LimiteDiario as e:
            res["estado"], res["error"] = "limite", str(e)
        except Bloqueado as e:
            res["estado"], res["error"] = "bloqueado", str(e)
        except Exception as e:
            res["estado"], res["error"] = "error", f"{type(e).__name__}: {e}"

        # Si la tienda bloqueó o falló, se conservan los últimos datos buenos marcados como anteriores.
        if res["estado"] != "ok" and not res["candidatos"]:
            ant = _previo(previo, item["id"], mod.TIENDA)
            if ant and ant.get("candidatos"):
                res["candidatos"] = ant["candidatos"]
                res["datos_de"] = ant.get("datos_de") or previo.get("generado")

        if urlparse(getattr(mod, "BASE", "")).netloc in cli.via_firecrawl:
            res["via"] = "firecrawl"

        orden = {"mismo": 0, "posible": 1, "alternativa": 2, "distinto": 3}
        res["candidatos"].sort(key=lambda c: (orden[c["veredicto"]], -c["puntajes"]["total"]))
        for c in res["candidatos"]:
            print(f"   {c['veredicto']:11} {c['puntajes']['total']:5}  {c['nombre']} ${c['precio']}")
        if res.get("error"):
            print(f"   ! {res['error']}")
        salida["competidores"].append(res)
    return salida


def _previo(previo: dict, pid: str, tienda: str) -> dict | None:
    for p in previo.get("productos", []):
        if p.get("id") == pid:
            return next((c for c in p.get("competidores", []) if c.get("tienda") == tienda), None)
    return None


def main() -> int:
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    previo = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {}
    iva = cat.get("iva", 0.19)
    cli = Cliente()
    productos = []
    for item in cat["productos"]:
        try:
            productos.append(procesar(cli, item, iva, previo))
        except Exception as e:
            print(f"! {item['id']}: {e}", file=sys.stderr)
            ant = next((p for p in previo.get("productos", []) if p.get("id") == item["id"]), None)
            if ant:
                productos.append(ant)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "iva": iva, "productos": productos}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"✓ {SALIDA.relative_to(RAIZ.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
