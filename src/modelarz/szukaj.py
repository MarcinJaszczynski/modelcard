"""Od nazwy do modelu: wyszukanie informacji i rysunków w sieci, ułożenie faktów przez model
językowy (lokalny LM Studio albo dowolny darmowy serwer zgodny z API OpenAI), budowa i kontrola.

Model językowy nie rysuje geometrii — podaje kilkanaście faktów (wymiary, kolory, napisy),
a bryłę składa z nich szablon kategorii. Dzięki temu wynik zawsze przechodzi przez te same
kontrole co modele wbudowane, a błędne dane wracają do modelu językowego z opisem błędu.

Ustawienia (zmienne środowiskowe):
  MODELARZ_LLM_URL    adres API, domyślnie http://localhost:1234/v1 (LM Studio)
  MODELARZ_LLM_MODEL  nazwa modelu; domyślnie pierwszy dostępny model czatu
  MODELARZ_LLM_KEY    klucz, jeśli serwer go wymaga (np. darmowe progi chmurowe)"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request

from .models import USER_DIR, entry
from .project import build_project
from .validate import validate

UA = {"User-Agent": "Modelarz/0.1 (projektowanie modeli kartonowych; uzytek prywatny)"}

SCHEMA = """Kategorie i pola (wszystkie wymiary ORYGINAŁU w metrach, kolory jako #rrggbb):

"czolg": {"template":"czolg","nazwa":str,"wariant":str,"scale":25..35,
  "dlugosc_kadluba":float (bez lufy),"szerokosc":float,"wysokosc_kadluba":float (do dachu kadłuba, bez wieży),
  "przeswit":float,"szerokosc_gasienicy":float,
  "wieza":{"x":float (środek wieży, od przodu kadłuba),"dlugosc":float,"szerokosc":float,"wysokosc":float},
  "lufa":{"dlugosc":float (wystająca przed wieżę),"kaliber":float},
  "kola":{"liczba":int (kół nośnych na stronę),"promien":float},
  "kolor":str,"napisy":[{"tekst":str,"miejsce":"wieza"|"kadlub","wysokosc":float,"kolor":str,"dx":float}]}

"samochod": {"template":"samochod","nazwa":str,"wariant":str,"scale":24,
  "nadwozie":"fastback"|"hatchback"|"sedan"|"kombi","dlugosc":float,"szerokosc":float,"wysokosc":float,
  "rozstaw_osi":float,"promien_kola":float,"przeswit":float,"linia_okien":float (wysokość dolnej krawędzi szyb),
  "kolor":str, "odwroc_profil": bool (true, gdy sylwetka z planu wyszła tyłem do przodu)}

"samolot": {"template":"samolot","nazwa":str,"wariant":str,"scale":33,
  "wzor":"bf109e"|"p51d" (bliższy układem jednosilnikowy dolnopłat),"dlugosc":float,"rozpietosc":float,
  "kolor_gora":str,"kolor_dol":str,"kolor_kolpaka":str,"znak":"balkenkreuz"|"us_star"|"roundel_pl"|""}
"""

EXAMPLE = {"template": "czolg", "nazwa": "M4A1 Sherman", "wariant": "1. Dywizja Pancerna, 1944", "scale": 30,
           "dlugosc_kadluba": 5.84, "szerokosc": 2.62, "wysokosc_kadluba": 1.75, "przeswit": 0.43,
           "szerokosc_gasienicy": 0.42, "wieza": {"x": 2.6, "dlugosc": 1.9, "szerokosc": 1.7, "wysokosc": 0.75},
           "lufa": {"dlugosc": 2.2, "kaliber": 0.075}, "kola": {"liczba": 6, "promien": 0.25}, "kolor": "#55593a",
           "napisy": [{"tekst": "17", "miejsce": "wieza", "wysokosc": 0.3, "kolor": "#f4f4f0", "dx": 0.0}]}
SYSTEM = "Jesteś dokumentalistą wydawnictwa modeli kartonowych. Odpowiadasz samym JSON-em."


def _get(url: str, timeout: float = 15.0):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def plan(query: str) -> dict:
    """Lokalny model rozpoznaje, o jaki obiekt chodzi, i układa zapytania do wyszukiwarki."""
    fallback = {"obiekt": query, "kontekst": "", "plany": [f"{query} blueprint drawing", f"{query} plany rysunki"],
                "malowanie": [f"{query} malowanie kamuflaż profil"], "dane": [f"{query} dane techniczne wymiary"],
                "modele": [f"{query} model kartonowy arkusze"]}
    try:
        out = _json(llm([{"role": "system", "content": SYSTEM}, {"role": "user", "content":
            f"Użytkownik chce zbudować model kartonowy: „{query}”. Zwróć JSON: "
            '{"obiekt": dokładna nazwa typu pojazdu/samolotu/okrętu (np. "T-34-85"), '
            '"kontekst": konkretny egzemplarz, film, załoga lub jednostka, o którą chodzi (albo ""), '
            '"plany": [2 zapytania do wyszukiwarki grafiki o rysunki w rzutach / plany, po polsku i po angielsku], '
            '"malowanie": [2 zapytania o malowanie i oznaczenia tego egzemplarza], '
            '"dane": [2 zapytania o wymiary i dane techniczne], '
            '"modele": [1 zapytanie o gotowe modele kartonowe tego obiektu]}'}], max_tokens=450))
        return {**fallback, **{k: v for k, v in out.items() if v}}
    except Exception:
        return fallback


def find_sources(query: str) -> dict:
    """Źródła z całej sieci: artykuł z danymi, strony z wymiarami, plany, malowania, gotowe modele."""
    from ddgs import DDGS
    pl = plan(query)
    out = {"query": query, "plan": pl, "article": None, "web": [], "images": []}
    for lang in ("pl", "en"):
        api = f"https://{lang}.wikipedia.org/w/api.php?format=json&"
        try:
            hits = _get(api + "action=query&list=search&srlimit=3&srsearch=" + urllib.parse.quote(pl["obiekt"]))
        except Exception:
            continue
        hits = hits.get("query", {}).get("search", [])
        if not hits:
            continue
        title = hits[0]["title"]
        t = urllib.parse.quote(title)
        text = _get(api + "action=query&prop=extracts&explaintext=1&titles=" + t)
        text = next(iter(text["query"]["pages"].values())).get("extract", "")
        try:
            box = _get(api + "action=parse&prop=wikitext&section=0&page=" + t)["parse"]["wikitext"]["*"]
        except Exception:
            box = ""
        out["article"] = {"title": title, "lang": lang, "url": f"https://{lang}.wikipedia.org/wiki/{t}",
                          "text": text[:4500], "infobox": box[:3500]}
        break
    ddg = DDGS()
    for q in pl["dane"][:2] + pl["malowanie"][:1]:
        try:
            for r in ddg.text(q, max_results=4, region="pl-pl"):
                if r.get("href") and all(r["href"] != w["url"] for w in out["web"]):
                    out["web"].append({"title": r.get("title", "")[:120], "url": r["href"], "snippet": r.get("body", "")[:400]})
        except Exception:
            pass
    seen = set()
    for group, label, n in (("plany", "Plany i rysunki", 5), ("malowanie", "Malowanie i oznaczenia", 4),
                            ("modele", "Gotowe modele", 4)):
        for q in pl[group][:2]:
            try:
                res = ddg.images(q, max_results=n)
            except Exception:
                continue
            for r in res:
                if r.get("thumbnail") and r.get("image") not in seen:
                    seen.add(r.get("image"))
                    out["images"].append({"group": label, "title": r.get("title", "")[:100], "thumb": r["thumbnail"],
                                          "image": r.get("image", ""), "page": r.get("url", "")})
    return out


def _image_parts(images: list, limit: int = 3) -> list:
    """Zaakceptowane plany jako obrazy dla modelu, który umie na nie patrzeć."""
    import base64
    parts = []
    for im in [i for i in images if i.get("group") == "Plany i rysunki"][:limit]:
        try:
            with urllib.request.urlopen(urllib.request.Request(im["thumb"], headers=UA), timeout=15) as r:
                data = base64.b64encode(r.read()).decode()
            parts.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data}})
        except Exception:
            continue
    return parts


def llm(messages: list, temperature: float = 0.2, max_tokens: int = 1500) -> str:
    base = os.environ.get("MODELARZ_LLM_URL", "http://localhost:1234/v1").rstrip("/")
    headers = {"Content-Type": "application/json", **UA}
    if os.environ.get("MODELARZ_LLM_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["MODELARZ_LLM_KEY"]
    model = os.environ.get("MODELARZ_LLM_MODEL")
    if not model:
        with urllib.request.urlopen(urllib.request.Request(base + "/models", headers=headers), timeout=10) as r:
            ids = [m["id"] for m in json.loads(r.read())["data"] if "embed" not in m["id"]]
        if not ids:
            raise RuntimeError("serwer modelu językowego nie udostępnia żadnego modelu czatu")
        model = ids[0]
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(base + "/chat/completions", body, headers), timeout=300) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except OSError as e:
        raise RuntimeError(f"nie udało się połączyć z modelem językowym pod {base} ({e}). Uruchom LM Studio "
                           "z załadowanym modelem albo ustaw MODELARZ_LLM_URL / MODELARZ_LLM_KEY.") from e


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("model językowy nie zwrócił obiektu JSON")
    return json.loads(m.group(0))


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "model"


def check(facts: dict) -> list[str]:
    """Buduje model z faktów i zwraca listę problemów (pusta = wszystko w porządku)."""
    if facts.get("template") == "czolg":   # zdrowy rozsądek, którego nie sprawdzi geometria
        try:
            if facts["wysokosc_kadluba"] > 0.72 * facts["szerokosc"]:
                return ["wysokosc_kadluba jest za duża względem szerokości — to wysokość do dachu kadłuba BEZ wieży"]
            if facts["wieza"]["wysokosc"] > 0.8 * facts["wysokosc_kadluba"]:
                return ["wieza.wysokosc jest za duża — to wysokość samej wieży ponad dachem kadłuba"]
        except (KeyError, TypeError) as e:
            return [f"brakuje pola: {e}"]
    try:
        title, cls, build = entry(facts)
        pr = build_project(build(cls()))
    except Exception as e:
        return [f"nie da się zbudować: {type(e).__name__}: {e}"]
    return [f"{c.name}: {c.detail}" for c in validate(pr) if not c.ok]


def _solve(messages: list, tries: int = 3) -> tuple[dict, list[str]]:
    facts, problems = {}, ["brak odpowiedzi"]
    for _ in range(tries):
        reply = llm(messages)
        try:
            facts = _json(reply)
            problems = check(facts)
        except Exception as e:
            problems = [f"niepoprawny JSON: {e}"]
        if not problems:
            break
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "Ten opis nie przeszedł kontroli:\n- " + "\n- ".join(problems)
                      + "\nPopraw wartości i zwróć cały poprawiony JSON, nic więcej."}]
    return facts, problems


def create(query: str, sources: dict, options: str = "") -> tuple[str, dict, list[str]]:
    """Układa fakty o obiekcie z zaakceptowanych źródeł i zapisuje opis modelu.
    Zwraca (nazwa pliku, fakty, problemy)."""
    art = sources.get("article") or {}
    pl = sources.get("plan", {})
    web = "\n".join(f"- {w['title']}: {w['snippet']}" for w in sources.get("web", []) if w.get("accepted", True))
    images = [i for i in sources.get("images", []) if i.get("accepted", True)]
    msg = (f"Zapytanie użytkownika: {query}\nObiekt: {pl.get('obiekt', query)}. Kontekst: {pl.get('kontekst', '')}\n"
           f"{('Życzenia: ' + options) if options else ''}\n\n"
           f"Artykuł „{art.get('title', '')}”:\n{art.get('infobox', '')}\n\n{art.get('text', '')}\n\n"
           f"Znalezione w sieci:\n{web}\n\n{SCHEMA}\n"
           f"Przykład FORMATU (inny pojazd — nie przepisuj jego wartości):\n{json.dumps(EXAMPLE, ensure_ascii=False)}\n\n"
           "Wybierz kategorię pasującą do zapytania i zwróć WYŁĄCZNIE jeden obiekt JSON z faktami. "
           "Wymiary bierz ze źródeł i z załączonych rysunków; czego w nich nie ma, podaj z własnej wiedzy o tym obiekcie. "
           "Jeśli zapytanie dotyczy konkretnego egzemplarza (film, pilot, jednostka), ustaw jego kolory i napisy.")
    parts = _image_parts(images)
    facts, problems = {}, []
    if parts:
        try:
            facts, problems = _solve([{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": [{"type": "text", "text": msg}] + parts}])
        except Exception:
            facts = {}   # model bez obsługi obrazów — próbujemy samym tekstem
    if not facts:
        facts, problems = _solve([{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}])
    if not facts.get("template"):
        return "", facts, problems or ["model językowy nie rozpoznał kategorii"]
    name = slug(facts.get("nazwa", query) + " " + facts.get("wariant", ""))
    outline_from = _outline(facts, images, name)
    facts["zrodla"] = {"zapytanie": query, "artykul": art.get("url", ""), "obrys_z_planu": outline_from,
                       "strony": [w["url"] for w in sources.get("web", []) if w.get("accepted", True)],
                       "obrazy": [{"grupa": i["group"], "strona": i["page"], "obraz": i.get("image", "")} for i in images]}
    save(name, facts)
    return name, facts, problems


def _outline(facts: dict, images: list, name: str) -> str:
    """Sylwetka boczna z pierwszego zaakceptowanego planu, na którym da się ją rozpoznać (na razie samochody)."""
    if facts.get("template") != "samochod":
        return ""
    from .obrys import views
    for im in [i for i in images if i.get("group") == "Plany i rysunki"]:
        for url in (im.get("image"), im.get("thumb")):
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read(8_000_000)
                v = views(data, facts["dlugosc"], facts["wysokosc"], facts["szerokosc"])
            except Exception:
                continue
            if not v:
                continue
            pts, png = v["side"], v["preview"]
            L, H = facts["dlugosc"], facts["wysokosc"]
            if min(z for x, z in pts if 0.05 * L <= x <= 0.95 * L) < 0.4 * H:
                continue          # dziura w sylwetce (np. niewidoczna linia maski) — ten rysunek się nie nadaje
            extra = {"profil_gora": pts, **({"obrys_gora": v["top"]} if v["top"] else {}),
                     **({"obrys_przod": v["front"]} if v["front"] else {})}
            if check({**facts, **extra}):
                extra = {"profil_gora": pts}          # rzuty z góry / z przodu psują bryłę — zostaje sam bok
                if check({**facts, **extra}):
                    continue                          # z tym obrysem model nie przechodzi kontroli — szukamy dalej
            facts.update(extra)
            USER_DIR.mkdir(exist_ok=True)
            if png:
                (USER_DIR / f"{name}_obrys.png").write_bytes(png)
            return im.get("page") or url
    return ""


def revise(name: str, remarks: str) -> tuple[dict, list[str]]:
    """Poprawia zapisany opis według uwag użytkownika."""
    path = USER_DIR / f"{name}.json"
    facts = json.loads(path.read_text(encoding="utf-8"))
    src = facts.pop("zrodla", None)
    new, problems = _solve([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{SCHEMA}\nObecny opis modelu:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
                                    f"Uwagi użytkownika do poprawy: {remarks}\n\n"
                                    "Zwróć cały poprawiony JSON (te same pola), nic więcej."}])
    if not problems and new.get("template"):
        if src:
            new["zrodla"] = src
        save(name, new)
        return new, []
    return facts, problems or ["model językowy nie zwrócił poprawnego opisu"]


def save(name: str, facts: dict) -> None:
    USER_DIR.mkdir(exist_ok=True)
    (USER_DIR / f"{name}.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
