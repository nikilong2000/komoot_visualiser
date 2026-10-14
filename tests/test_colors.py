from komoot_visualiser.colors import TOUR_COLORS, color_for_tour

PALETTE = {(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)) for color in TOUR_COLORS}


def test_gives_the_same_tour_the_same_palette_colour():
    assert color_for_tour("123456789") == color_for_tour("123456789")
    assert color_for_tour("123456789") in PALETTE
    assert color_for_tour("manual/morning-ride") in PALETTE


def test_spreads_tours_across_the_whole_palette():
    assert {color_for_tour(str(1_000_000_000 + i)) for i in range(200)} == PALETTE
