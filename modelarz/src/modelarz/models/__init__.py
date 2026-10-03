from .p51 import P51Params, build_p51
from .simple import BoxParams, FrustumParams, HouseParams, build_box, build_frustum, build_house

# nazwa -> (tytuł, klasa parametrów, funkcja budująca)
REGISTRY = {
    "pudelko": ("Pudełko", BoxParams, build_box),
    "domek": ("Domek z dachem dwuspadowym", HouseParams, build_house),
    "walec": ("Walec / stożek ścięty", FrustumParams, build_frustum),
    "p51": ("Samolot typu P-51", P51Params, build_p51),
}
