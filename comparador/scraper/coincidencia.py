"""Compara dos productos por características técnicas, descripción y foto."""
from __future__ import annotations

import io
import re
import unicodedata

from rapidfuzz import fuzz

NUM = r"(\d+(?:[.,]\d+)?)"
# Prefijos habituales de circuitos integrados de potencia / módulos.
RE_CHIP = re.compile(r"\b((?:LM|XL|MP|TPS|SY|MT|AMS|LTC|LT|MC|TP|IP|SX|ME|LMR|DFR)\d{3,5}[A-Z]{0,2})\b")

PESOS = {"specs": 0.5, "descripcion": 0.3, "foto": 0.2}

VACIAS = set("""a al con de del el en es la las lo los para por que se su un una y o e
modulo conversor regulador ajustable reductor dc dc-dc voltaje tension salida entrada hasta
ideal alta alto bajo muy tu tus este esta puede permite como mas the and for""".split())


def _f(x: str) -> float:
    return float(x.replace(",", "."))


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


# ---------------- extracción de características ----------------

def extraer_specs(nombre: str, descripcion: str, sku: str = "", url: str = "") -> dict:
    texto = f"{nombre}\n{descripcion}"
    lineas = [l for l in re.split(r"\n|(?<=[.;])\s+|\s+\*\s+|•", texto) if l.strip()]
    sp: dict = {}

    chips = set(RE_CHIP.findall(f"{sku} {nombre} {descripcion} {url}".upper().replace("-", " ").replace("_", " ")))
    chips |= set(RE_CHIP.findall(re.sub(r"[\s\-_]", "", f"{sku} {nombre}".upper())))
    if chips:
        sp["chips"] = sorted(chips)

    # Corriente: la primera cifra en amperios que aparece justo después de la palabra "corriente".
    for m in re.finditer(r"corriente|current", _norm(texto)):
        a = _amperios(texto[m.end():m.end() + 60])
        if a:
            sp["corriente_a"] = a[0]
            break
    if "corriente_a" not in sp:
        a = _amperios(nombre) or _amperios(texto)
        if a:
            sp["corriente_a"] = max(a)

    # Rangos de voltaje: se clasifican por la palabra "entrada" / "salida" en la misma línea.
    rango = re.compile(NUM + r"\s*v?\s*(?:a|~|-|–|hasta|to)\s*" + NUM + r"\s*v(?:dc|cc)?\b", re.I)
    for l in lineas:
        nl = _norm(l)
        for m in rango.finditer(l):
            lo, hi = sorted((_f(m.group(1)), _f(m.group(2))))
            antes = nl[:m.start()]   # la palabra clave más cercana antes del rango decide si es entrada o salida
            pe = max(antes.rfind("entrada"), antes.rfind("input"))
            ps = max(antes.rfind("salida"), antes.rfind("output"))
            clave = "vin" if pe > ps else "vout" if ps > pe else None
            if clave:
                prev = sp.get(clave)
                sp[clave] = [min(lo, prev[0]), max(hi, prev[1])] if prev else [lo, hi]
    if "vout" not in sp:   # p. ej. el nombre "Reductor 0-24v 5A"
        m = rango.search(nombre)
        if m:
            sp["vout"] = sorted((_f(m.group(1)), _f(m.group(2))))

    m = re.search(NUM + r"\s*khz", texto, re.I)
    if m:
        sp["frecuencia_khz"] = _f(m.group(1))
    for l in lineas:   # potencia nominal (no los umbrales tipo "mayor a 10W")
        m = re.search(NUM + r"\s*w\b", l, re.I)
        if m and not re.search(r"mayor|menor|mas de|menos de", _norm(l)):
            sp["potencia_w"] = _f(m.group(1))
            break
    m = re.search(NUM + r"\s*%", texto)
    if m and "eficiencia" in _norm(texto):
        sp["eficiencia_pct"] = _f(m.group(1))
    m = re.search(NUM + r"\s*(?:mm)?\s*[x×*]\s*" + NUM + r"\s*(?:mm)?(?:\s*[x×*]\s*" + NUM + r")?\s*mm", texto, re.I)
    if m:
        sp["dimensiones_mm"] = sorted((_f(g) for g in m.groups() if g), reverse=True)
    return sp


def _amperios(t: str) -> list[float]:
    vals = [_f(x) for x in re.findall(NUM + r"\s?A\b", t)]
    vals += [_f(x) / 1000 for x in re.findall(NUM + r"\s?mA\b", t)]
    vals += [_f(x) for x in re.findall(NUM + r"\s*amperios", t, re.I)]
    return vals


# ---------------- puntajes ----------------

def _solape(a, b) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 1.0


def _cerca(a: float, b: float) -> float:
    return min(a, b) / max(a, b) if max(a, b) else 1.0


def puntaje_specs(a: dict, b: dict) -> tuple[float | None, list[str], bool]:
    """Devuelve (puntaje 0-100, motivos, hay_conflicto)."""
    partes, motivos, conflicto = [], [], False

    if a.get("chips") and b.get("chips"):
        ca, cb = set(a["chips"]), set(b["chips"])
        if ca == cb:
            partes.append(1.0); motivos.append(f"mismo chip {', '.join(ca)}")
        elif ca & cb:
            partes.append(0.5); motivos.append(f"chip ambiguo: {', '.join(sorted(cb))}")
        else:
            partes.append(0.0); conflicto = True
            motivos.append(f"chip distinto: {', '.join(sorted(ca))} vs {', '.join(sorted(cb))}")

    if a.get("corriente_a") and b.get("corriente_a"):
        r = _cerca(a["corriente_a"], b["corriente_a"])
        partes.append(r)
        if r < 0.7:
            conflicto = True
            motivos.append(f"corriente distinta: {a['corriente_a']:g} A vs {b['corriente_a']:g} A")
        else:
            motivos.append(f"corriente similar ({b['corriente_a']:g} A)")

    for k, txt in (("vin", "entrada"), ("vout", "salida")):
        if a.get(k) and b.get(k):
            s = _solape(a[k], b[k]); partes.append(s)
            motivos.append(f"{txt} {b[k][0]:g}-{b[k][1]:g} V ({round(s * 100)} % de solape)")

    for k in ("frecuencia_khz", "potencia_w"):
        if a.get(k) and b.get(k):
            partes.append(_cerca(a[k], b[k]))

    if a.get("dimensiones_mm") and b.get("dimensiones_mm"):
        da, db = a["dimensiones_mm"][:2], b["dimensiones_mm"][:2]
        partes.append(sum(_cerca(x, y) for x, y in zip(da, db)) / len(da))

    if not partes:
        return None, ["sin características comparables"], False
    return round(100 * sum(partes) / len(partes), 1), motivos, conflicto


def _palabras(t: str) -> str:
    t = re.sub(r"[^a-z0-9. ]", " ", _norm(t))
    return " ".join(w for w in t.split() if w not in VACIAS and len(w) > 1)


def puntaje_descripcion(nombre_a: str, desc_a: str, nombre_b: str, desc_b: str) -> float:
    n = fuzz.token_set_ratio(_palabras(nombre_a), _palabras(nombre_b))
    d = fuzz.token_set_ratio(_palabras(desc_a)[:2000], _palabras(desc_b)[:2000]) if desc_a and desc_b else n
    return round(0.4 * n + 0.6 * d, 1)


def puntaje_foto(img_a: bytes | None, img_b: bytes | None) -> float | None:
    """Similitud de imagen con hash perceptual (0-100). None si falta alguna foto."""
    if not img_a or not img_b:
        return None
    try:
        import imagehash
        from PIL import Image
        ia, ib = (Image.open(io.BytesIO(x)).convert("RGB") for x in (img_a, img_b))
        d = (imagehash.phash(ia) - imagehash.phash(ib)) + (imagehash.dhash(ia) - imagehash.dhash(ib))
        return round(max(0.0, 100 * (1 - d / 64)), 1)   # 0 = idénticas … 64+ = muy distintas
    except Exception:
        return None


def combinar(specs: float | None, desc: float | None, foto: float | None, conflicto: bool) -> tuple[float, str]:
    valores = {"specs": specs, "descripcion": desc, "foto": foto}
    usados = {k: v for k, v in valores.items() if v is not None}
    total = sum(PESOS[k] * v for k, v in usados.items()) / sum(PESOS[k] for k in usados) if usados else 0.0
    total = round(total, 1)
    if conflicto:
        veredicto = "alternativa" if total >= 45 else "distinto"
    elif total >= 80:
        veredicto = "mismo"
    elif total >= 60:
        veredicto = "posible"
    else:
        veredicto = "distinto"
    return total, veredicto
