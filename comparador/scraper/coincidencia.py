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
    modelos = modelos_de(sku, nombre)
    if modelos:
        sp["modelos"] = modelos

    # Corriente: primero "corriente de salida"; si no hay, la primera cifra después de "corriente".
    nt = _norm(texto)
    for patron in (r"corriente (?:maxima |pico |nominal )?de salida|output current", r"corriente|current"):
        for m in re.finditer(patron, nt):
            a = _amperios(texto[m.end():m.end() + 60])
            if a:
                sp["corriente_a"] = a[0]
                break
        if "corriente_a" in sp:
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


UNIDAD = re.compile(r"\d+(?:[.,]\d+)?(?:V|A|W|MA|MAH|KHZ|HZ|MM|CM|VDC|VAC|VCC|KV|KW|MW|UF|NF|PF|G|KG|M|MP|P|GB|TB|CH)", re.I)


def modelos_de(sku: str, nombre: str) -> list[str]:
    """Códigos de modelo (letras + números) de la referencia y del nombre: XL6009, UT33C+, TAR-XL6009…"""
    out = []
    for tok in re.split(r"[\s,;()/|\[\]]+", f"{sku} {nombre}"):
        t = re.sub(r"[^A-Z0-9+]", "", tok.upper())
        if len(t) >= 4 and re.search(r"\d", t) and re.search(r"[A-Z]", t) and not UNIDAD.fullmatch(t) \
                and not re.fullmatch(r"\d+(?:V|A|W)?\d*(?:V|A|W)", t):
            if t not in out:
                out.append(t)
    return out


def _mismo_modelo(a: list[str], b: list[str]) -> str:
    for x in a:
        for y in b:
            if x == y or (len(x) >= 5 and x in y) or (len(y) >= 5 and y in x):
                return x
    return ""


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

    if a.get("modelos") and b.get("modelos"):
        m = _mismo_modelo(a["modelos"], b["modelos"])
        if m:
            partes.append(1.0); motivos.append(f"mismo modelo {m}")

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


# Palabras que distinguen variantes de un mismo modelo (con display, con cámara, kit, cable de 4 m…).
VARIANTES = {
    "display": r"display|pantalla",
    "camara": r"camara|\bcam\b|ov2640",
    "kit": r"\bkit\b|combo",
    "bateria": r"bateria",
    "sonda": r"sonda|prueba de agua|impermeable|waterproof",
}


def _longitud_cable(t: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|mts?|metros?)\b", _norm(t))
    return _f(m.group(1)) if m else None


def diferencias_variante(nombre_a: str, nombre_b: str) -> list[str]:
    """Rasgos que tiene un nombre y el otro no (p. ej. «display»), y largo de cable distinto."""
    na, nb = _norm(nombre_a), _norm(nombre_b)
    dif = [k for k, rx in VARIANTES.items() if bool(re.search(rx, na)) != bool(re.search(rx, nb))]
    la, lb = _longitud_cable(nombre_a), _longitud_cable(nombre_b)
    if la and lb and abs(la - lb) > 0.01:
        dif.append(f"cable {la:g} m vs {lb:g} m")
    return dif


def misma_referencia(sku_a: str, sku_b: str) -> bool:
    """La referencia de Suconel aparece en la del competidor (o al revés): HC06 ↔ BT-HC-06, XL6009 ↔ TAR-XL6009."""
    a, b = (re.sub(r"[^A-Z0-9+]", "", (x or "").upper()) for x in (sku_a, sku_b))
    if len(a) < 4 or len(b) < 4:
        return a == b and bool(a)
    return a == b or a in b or b in a


def coincidencia_fuerte(a: dict, b: dict, ps: float | None, sku_a: str = "", sku_b: str = "",
                        nombre_a: str = "", nombre_b: str = "") -> bool:
    """¿Es el mismo producto? Exige que no haya diferencias de variante y además:
    - la misma referencia (SKU) con características compatibles, o
    - el mismo chip con al menos 3 características casi iguales y las mismas medidas."""
    if diferencias_variante(nombre_a, nombre_b):
        return False
    da, db = a.get("dimensiones_mm"), b.get("dimensiones_mm")
    if da and db and any(_cerca(x, y) < 0.85 for x, y in zip(da[:2], db[:2])):
        return False
    if misma_referencia(sku_a, sku_b) and (ps is None or ps >= 70):
        return True
    comunes = sum(1 for k in ("corriente_a", "vin", "vout", "frecuencia_khz", "potencia_w", "dimensiones_mm") if a.get(k) and b.get(k))
    mismo_chip = bool(a.get("chips")) and set(a.get("chips", [])) == set(b.get("chips", []))
    return mismo_chip and comunes >= 3 and ps is not None and ps >= 90


def combinar(specs: float | None, desc: float | None, foto: float | None, conflicto: bool,
             fuerte: bool = False) -> tuple[float, str]:
    valores = {"specs": specs, "descripcion": desc, "foto": foto}
    usados = {k: v for k, v in valores.items() if v is not None}
    total = sum(PESOS[k] * v for k, v in usados.items()) / sum(PESOS[k] for k in usados) if usados else 0.0
    total = round(total, 1)
    if conflicto:
        veredicto = "alternativa" if total >= 45 else "distinto"
    elif fuerte or total >= 80:
        veredicto = "mismo"
    elif total >= 60:
        veredicto = "posible"
    else:
        veredicto = "distinto"
    return total, veredicto
