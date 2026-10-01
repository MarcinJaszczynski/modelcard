# Kartonowy Modelarz

Aplikacja generująca plansze modeli kartonowych: bryła → unfolding → SVG/PDF, korpus skanów, sugestie CV.

## Start

```bash
cd ~/Projects/kartonowy-modelarz
php artisan serve --port=8010
# http://127.0.0.1:8010/admin  ·  admin@example.com / password
```

## Demo

```bash
php artisan modelarz:demo-box --shape=building --markings=1 --style=dirt
php artisan modelarz:demo-box --shape=wagon --markings=1
php artisan modelarz:demo-box --shape=box --width=200 --height=120 --depth=150 --multisheet=1
php artisan modelarz:demo-analyze
```

## Funkcje

- Bryły: box · cylinder · building · wagon
- Style: clean · dirt · rust · dust
- Markings: okna/drzwi (building, wagon)
- Multi-arkusz: packing paneli gdy net nie mieści się / wymuszony
- Faza 3: **Analizuj skan** → overlay cut/fold (do weryfikacji)
