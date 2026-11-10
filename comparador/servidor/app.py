"""Servidor del comparador de precios (se despliega en Render).

Rutas:
  GET  /salud               -> {"ok": true}  (lo usa Render y el "despertador" de GitHub Actions)
  POST /comparar {"url": …} -> compara un producto de Suconel con las otras tiendas.
                               Requiere el token de Firebase de un usuario aprobado.

Variables de entorno:
  FIREBASE_SERVICE_ACCOUNT  JSON de la cuenta de servicio de Firebase (secreta)
  ORIGENES_PERMITIDOS       orígenes separados por coma (por defecto el sitio de GitHub Pages)
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from fastapi import FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth, credentials, firestore
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))
from comparar import procesar  # noqa: E402
from tiendas.base import Cliente  # noqa: E402

RE_SUCONEL = re.compile(r"^https://(www\.)?suconel\.com/productos/[a-z0-9\-]+/?$")
LIMITE_POR_HORA = 20          # comparaciones por usuario por hora
IVA = 0.19
COMPETIDORES = {"didacticas": {"maximo": 5}}

app = FastAPI(title="Comparador de precios Suconel")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "ORIGENES_PERMITIDOS", "https://andrest08m.github.io,http://localhost:8000,http://localhost:8765").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_db = None
_lock = threading.Lock()                  # una comparación a la vez: no saturar las tiendas
_uso: dict[str, list[float]] = {}


def db():
    """Inicializa Firebase Admin con la cuenta de servicio (una sola vez)."""
    global _db
    if _db is None:
        crudo = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if not crudo:
            raise HTTPException(500, "Falta la variable FIREBASE_SERVICE_ACCOUNT en Render.")
        firebase_admin.initialize_app(credentials.Certificate(json.loads(crudo)))
        _db = firestore.client()
    return _db


def usuario_aprobado(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Inicia sesión para comparar productos.")
    base = db()
    try:
        tok = auth.verify_id_token(authorization[7:])
    except Exception:
        raise HTTPException(401, "Tu sesión expiró. Vuelve a iniciar sesión.")
    perfil = base.collection("users").document(tok["uid"]).get()
    datos = perfil.to_dict() if perfil.exists else {}
    if datos.get("estado") != "aprobado":
        raise HTTPException(403, "Tu cuenta aún no está aprobada.")
    return {"uid": tok["uid"], **datos}


def limitar(uid: str):
    ahora = time.time()
    usos = [t for t in _uso.get(uid, []) if ahora - t < 3600]
    if len(usos) >= LIMITE_POR_HORA:
        raise HTTPException(429, f"Máximo {LIMITE_POR_HORA} comparaciones por hora.")
    _uso[uid] = usos + [ahora]


def id_producto(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1][:120]


class Pedido(BaseModel):
    url: str


@app.get("/")
def inicio():
    return {"ok": True, "servicio": "Comparador de precios Suconel", "uso": "POST /comparar desde la página del comparador"}


@app.get("/salud")
def salud():
    return {"ok": True}


@app.post("/comparar")
async def comparar(pedido: Pedido, authorization: str | None = Header(None)):
    url = pedido.url.strip().split("?")[0].split("#")[0]
    if not RE_SUCONEL.match(url):
        raise HTTPException(400, "Pega la URL de un producto de suconel.com (https://suconel.com/productos/…).")
    u = usuario_aprobado(authorization)
    limitar(u["uid"])
    pid = id_producto(url)
    item = {"id": pid, "suconel": url, "competidores": COMPETIDORES}

    def trabajo():
        with _lock:
            return procesar(Cliente(), item, IVA, previo=_previo(pid))

    try:
        res = await run_in_threadpool(trabajo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"No se pudo leer el producto en Suconel ({type(e).__name__}).")

    res["generado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["pedido_por"] = u.get("username", u["uid"])
    db().collection("precios").document(pid).set(res)
    return res


def _previo(pid: str) -> dict:
    """Último resultado guardado: si una tienda bloquea, se muestran esos datos marcados como anteriores."""
    try:
        d = db().collection("precios").document(pid).get()
        if d.exists:
            p = d.to_dict()
            return {"generado": p.get("generado"), "productos": [p]}
    except Exception:
        pass
    return {}
