"""Respaldo con Firecrawl cuando una tienda bloquea (sin red: transporte simulado)."""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tiendas import base  # noqa: E402
from tiendas.base import Bloqueado, Cliente  # noqa: E402

TIENDA = "https://www.didacticaselectronicas.com/shop/x-1"


def cliente(firecrawl_resp, key="fc-test"):
    llamadas = []

    def manejar(req: httpx.Request):
        llamadas.append(req)
        if req.url.host == "api.firecrawl.dev":
            assert req.headers["authorization"] == "Bearer fc-test"
            assert json.loads(req.content)["url"] == TIENDA
            return firecrawl_resp
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403, text="Forbidden")

    c = Cliente(firecrawl_key=key)
    c.http = httpx.Client(transport=httpx.MockTransport(manejar))
    c._esperar = lambda url: None
    return c, llamadas


@pytest.fixture(autouse=True)
def reiniciar_cupo(monkeypatch):
    monkeypatch.setitem(base._uso_firecrawl, "n", 0)


def test_sin_clave_queda_bloqueado():
    c, _ = cliente(None, key="")
    with pytest.raises(Bloqueado, match="403"):
        c.html(TIENDA)


def test_usa_firecrawl_si_bloquea():
    ok = httpx.Response(200, json={"success": True, "data": {"rawHtml": "<h1>Hola</h1>", "metadata": {"statusCode": 200}}})
    c, llamadas = cliente(ok)
    assert c.html(TIENDA) == "<h1>Hola</h1>"
    assert "www.didacticaselectronicas.com" in c.via_firecrawl
    # la segunda vez va directo a Firecrawl, sin volver a intentar la tienda
    n = len(llamadas)
    c.html(TIENDA)
    assert [r.url.host for r in llamadas[n:]] == ["api.firecrawl.dev"]


def test_firecrawl_sin_creditos():
    c, _ = cliente(httpx.Response(402, json={"success": False, "error": "Payment required"}))
    with pytest.raises(Bloqueado, match="créditos"):
        c.html(TIENDA)


def test_firecrawl_tambien_bloqueado():
    resp = httpx.Response(200, json={"success": True, "data": {"rawHtml": "<p>captcha</p>", "metadata": {"statusCode": 403}}})
    c, _ = cliente(resp)
    with pytest.raises(Bloqueado, match="también"):
        c.html(TIENDA)


def test_limite_diario(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_MAX_DIA", "1")
    ok = httpx.Response(200, json={"success": True, "data": {"rawHtml": "<p>x</p>"}})
    c, _ = cliente(ok)
    c.html(TIENDA)
    with pytest.raises(Bloqueado, match="límite diario"):
        c.html(TIENDA)
