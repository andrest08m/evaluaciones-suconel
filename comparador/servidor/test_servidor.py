"""Pruebas del servidor sin red ni Firebase real (todo simulado)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
import app as servidor  # noqa: E402
from tiendas import didacticas  # noqa: E402

PAG = AQUI.parent / "scraper" / "tests" / "paginas"
U_SUC = "https://suconel.com/productos/modulo-regulador-dc-dc-ajustable-lm-2596"
MAPA = {
    U_SUC: "suconel_lm2596.html",
    "https://www.didacticaselectronicas.com/shop/lm2596-v-5a-conversor-dc-dc-reductor-0-24v-5a-xl4005-6792": "didacticas_lm2596_v_5a.html",
    "https://www.didacticaselectronicas.com/shop/xl4015-5a-modulo-conversor-dc-dc-xl4015-salida-ajustable-5a-52118": "didacticas_xl4015.html",
}


class ClienteFalso:
    def html(self, u):
        return (PAG / MAPA[u]).read_text(encoding="utf-8")

    def bytes(self, u):
        raise RuntimeError("sin red")


class Doc:
    def __init__(self, data=None):
        self._d = data

    @property
    def exists(self):
        return self._d is not None

    def to_dict(self):
        return self._d


class BDFalsa:
    def __init__(self):
        self.guardado = {}
        self.users = {"u-ok": {"username": "laura", "estado": "aprobado"}, "u-pend": {"estado": "pendiente"}}

    def collection(self, nombre):
        bd = self

        class Col:
            def document(self, i):
                class D:
                    def get(self_):
                        return Doc(bd.users.get(i) if nombre == "users" else bd.guardado.get(i))

                    def set(self_, data):
                        bd.guardado[i] = data
                return D()
        return Col()


@pytest.fixture
def cli(monkeypatch):
    bd = BDFalsa()
    monkeypatch.setattr(servidor, "_db", bd)
    monkeypatch.setattr(servidor, "_uso", {})
    monkeypatch.setattr(servidor, "Cliente", ClienteFalso)
    monkeypatch.setattr(servidor.auth, "verify_id_token", lambda t: {"uid": t})
    monkeypatch.setattr(didacticas, "buscar", lambda c, t, maximo=8: didacticas.urls_de_busqueda((PAG / "didacticas_busqueda.html").read_text()))
    c = TestClient(servidor.app)
    c.bd = bd
    return c


def test_salud(cli):
    assert cli.get("/salud").json() == {"ok": True}


def test_requiere_login(cli):
    assert cli.post("/comparar", json={"url": U_SUC}).status_code == 401


def test_requiere_aprobado(cli):
    r = cli.post("/comparar", json={"url": U_SUC}, headers={"Authorization": "Bearer u-pend"})
    assert r.status_code == 403


def test_solo_suconel(cli):
    r = cli.post("/comparar", json={"url": "https://otra.com/x"}, headers={"Authorization": "Bearer u-ok"})
    assert r.status_code == 400


def test_compara_y_guarda(cli):
    r = cli.post("/comparar", json={"url": U_SUC + "?utm=x"}, headers={"Authorization": "Bearer u-ok"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == "modulo-regulador-dc-dc-ajustable-lm-2596"
    assert d["referencia"]["sku"] == "LM2596"
    cands = d["competidores"][0]["candidatos"]
    assert len(cands) == 2 and all(c["veredicto"] == "alternativa" for c in cands)
    assert d["pedido_por"] == "laura"
    assert cli.bd.guardado[d["id"]]["referencia"]["precio"] == 3135


def test_cors(cli):
    r = cli.options("/comparar", headers={"Origin": "https://andrest08m.github.io", "Access-Control-Request-Method": "POST",
                                          "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.headers.get("access-control-allow-origin") == "https://andrest08m.github.io"


def test_limite(cli, monkeypatch):
    monkeypatch.setattr(servidor, "LIMITE_POR_HORA", 1)
    h = {"Authorization": "Bearer u-ok"}
    assert cli.post("/comparar", json={"url": U_SUC}, headers=h).status_code == 200
    assert cli.post("/comparar", json={"url": U_SUC}, headers=h).status_code == 429
