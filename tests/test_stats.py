import numpy as np

from komoot_visualiser import stats


def test_step_lengths_follow_the_earths_curvature():
    assert stats.step_lengths_km(np.array([[8.0, 47.0], [8.0, 47.1]])).round(2).tolist() == [11.12]


def test_moving_time_leaves_out_stops_and_paused_recordings():
    # 10 km in 10 min, standing for 5 min, a 20-minute gap in the recording, then 1 km in 1 min
    steps_km = np.array([10.0, 0.0, 2.0, 1.0])
    seconds = np.array([0, 600, 900, 2100, 2160])

    assert stats.moving_seconds(steps_km, seconds) == 660


def test_elevation_change_adds_up_every_climb_and_descent():
    assert stats.elevation_change(np.array([100.0, 120.0, 110.0, 150.0, 140.0])) == (60.0, 20.0)


def test_profile_thins_out_long_tracks_but_keeps_both_ends():
    km, m = np.linspace(0, 10, 1001), np.linspace(500, 600, 1001)

    assert len(stats.profile(km[:5], m[:5])) == 5
    profile = stats.profile(km, m, points=50)
    assert (len(profile), profile[0], profile[-1]) == (50, (0.0, 500), (10.0, 600))


def test_reads_komoots_elevation_from_the_description():
    description = "Distance: 97.6km, Estimated duration: 9.58h, Elevation up: 1314.2m, Elevation down: 2010.0m"

    assert stats.komoot_elevation(description) == (1314.2, 2010.0)
    assert stats.komoot_elevation("A nice ride") is None
    assert stats.komoot_elevation(None) is None
