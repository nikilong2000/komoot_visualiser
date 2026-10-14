"""A stable, distinct colour per tour."""

#: Checked across all pairs (any two tours can lie side by side) against a light basemap (#f2f3f0):
#: contrast >= 3:1, colour-blind separation >= 8 ΔE, normal vision >= 15 ΔE.
TOUR_COLORS = ("#3245b7", "#b17000", "#14938d", "#ac1c0f", "#4285f4", "#881d83", "#056641", "#df4f70", "#ae55c1")


def hex_color_for_tour(tour_id: str) -> str:
    """Colour for a tour. Hashing the id keeps the colour when other tours are added or removed."""
    return TOUR_COLORS[_fnv1a(tour_id) % len(TOUR_COLORS)]


def color_for_tour(tour_id: str) -> tuple[int, int, int]:
    """The same colour as RGB, as the map layers want it."""
    hex_color = hex_color_for_tour(tour_id)
    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)


def _fnv1a(text: str) -> int:
    """32-bit FNV-1a hash (Python's own hash() changes between runs)."""
    value = 0x811C9DC5
    for byte in text.encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value
