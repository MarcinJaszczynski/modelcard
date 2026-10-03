# Modelarz

Projektowanie modeli kartonowych: **bryła 3D → rozwinięcia z zakładkami → arkusze PDF 1:1**.

Jedynym źródłem prawdy jest siatka 3D modelu. Rozwinięcia powstają przez sztywne
spłaszczanie jej ścian, szkielet przez cięcie tej samej bryły płaszczyznami, a arkusze
przez układanie części wyłącznie obrotami i przesunięciami (nigdy skalowaniem).

## Użycie

```bash
uv run modelarz serve                 # interfejs: http://127.0.0.1:8791
uv run modelarz build p51 --set scale=48 --page A4 -o out/p51
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
| `models/` | pudełko, domek, walec/stożek, samolot typu P-51 |

Nowy model to funkcja, która buduje `Mesh` (np. `mesh.loft()` między przekrojami)
i dopisuje się do `models.REGISTRY` — reszta potoku działa bez zmian.
