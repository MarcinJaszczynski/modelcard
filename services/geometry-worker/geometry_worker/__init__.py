"""
Geometry worker — deterministyczny pipeline kartonowy (MVP).

Wejście: parametry bryły → rozwinięcie z zakładkami → SVG A4.
"""

from .box_unfold import unfold_box
from .cli import main

__all__ = ["unfold_box", "main"]
