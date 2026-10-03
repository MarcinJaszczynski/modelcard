# Modelarz

Projektowanie modeli kartonowych: **bryła 3D → rozwinięcia z zakładkami → arkusze PDF 1:1**.

Jedynym źródłem prawdy jest siatka 3D modelu. Rozwinięcia powstają przez sztywne
spłaszczanie jej ścian, szkielet przez cięcie tej samej bryły płaszczyznami, a arkusze
przez układanie części wyłącznie obrotami i przesunięciami (nigdy skalowaniem).

## Użycie

```bash
uv run modelarz serve                 # interfejs: http://127.0.0.1:8791
uv run modelarz build bf109e --set scale=48 --set level=3 --page A4 -o out/bf109e
uv run modelarz list                  # modele i parametry
uv run pytest                         # bramka jakości
```

`build` zapisuje `arkusze.pdf` (części, podziałka kontrolna, instrukcja) i `podglad.html`
(bryła 3D). Gotowe przykłady są w `przyklady/`.

## Budowa

| moduł | rola |
|---|---|
| `mesh.py` | bryła: płaskie ściany w częściach, spawanie wierzchołków, orientacja, przekroje |
| `unfold.py` | rozwijanie części (izometryczne), linie zgięć, podział zbyt dużych części, znaczniki |
| `seams.py` | szwy z numerami, zakładki po jednej stronie, ząbki na krawędziach krzywych |
| `skeleton.py` | płyty szkieletu z przekrojów, pomniejszone o poszycie, wpusty pół na pół |
| `layout.py` | pakowanie na A4/A3 z obrotami, bez zmiany skali |
| `pdf.py`, `preview.py` | arkusze wektorowe i podgląd three.js |
| `validate.py` | kontrole: skala 1:1, długości szwów, samoprzecięcia, zakładki, nakładanie |
| `paint.py` | malowanie: warstwy z rzutów (kamuflaż, znaki, linie blach) przenoszone na rozwinięcia |
| `models/` | pudełko, domek, walec/stożek, generator samolotu z opisu |
| `samoloty/*.json` | opisy samolotów w danych: przekroje kadłuba, płaty, kabina, śmigło, podwozie, malowanie |

Nowy samolot to nowy plik w `src/modelarz/samoloty/` (wymiary oryginału w metrach) — pojawia się
sam na liście modeli; skalę i stopień trudności (1–3) wybiera się przy generowaniu.
Inna bryła to funkcja budująca `Mesh` dopisana do `models.REGISTRY`.
