"""Tests puros de las reglas del juego (sin Panda3D)."""

from __future__ import annotations

import random

from patinete_no_mueras.sim import (
    GREEN,
    LANE_X,
    MAX_LIVES,
    RED,
    START_ABS,
    STOP_LINE_GAP,
    VEHICLE_KMH,
    TrafficSim,
    Vehicle,
    bus_stop_y,
    light_state,
    overlaps,
    player_box,
    vehicle_box,
)


def make_sim(seed: int = 3) -> TrafficSim:
    sim = TrafficSim(random.Random(seed))
    sim.vehicles.clear()
    sim._ahead_timer = 1e9
    sim._behind_timer = 1e9
    sim._cross_timer = 1e9
    return sim


def run(
    sim: TrafficSim, seconds: float, steer: float = 0.0, brake: bool = False
) -> list:
    events = []
    steps = int(seconds * 60)
    for _ in range(steps):
        events.extend(sim.step(1 / 60, steer, brake))
    return events


def test_speed_limits_follow_the_brief() -> None:
    assert VEHICLE_KMH["bici"] == 20
    assert VEHICLE_KMH["colectivo"] == 60
    assert VEHICLE_KMH["auto"] == 80
    assert VEHICLE_KMH["taxi"] == 100
    assert 40 < VEHICLE_KMH["moto"] < VEHICLE_KMH["taxi"]


def test_light_cycle_has_three_states() -> None:
    states = {light_state(150.0, t / 10) for t in range(211)}
    assert states == {GREEN, "amarillo", RED}


def test_start_is_between_intersections() -> None:
    sim = TrafficSim(random.Random(1))
    assert sim.player_abs == START_ABS
    assert all(light.rel_y != 0 for light in sim.lights)


def test_player_reaches_cruise_and_brakes() -> None:
    sim = make_sim()
    run(sim, 6.0)
    assert 39.0 < sim.player_speed_kmh <= 40.0
    run(sim, 2.0, brake=True)
    assert sim.player_speed_kmh == 0.0


def test_steering_moves_the_scooter_and_curb_stops_it() -> None:
    sim = make_sim()
    sim.player_speed = 11.0
    run(sim, 1.0, steer=1.0)
    assert sim.player_x > 1.0
    events = run(sim, 4.0, steer=1.0)
    assert sim.player_x <= 4.85
    assert any(event.kind == "curb" for event in events)


def test_red_light_costs_points() -> None:
    sim = make_sim()
    sim.time = 10.0
    sim.player_abs = 139.0
    sim.player_speed = 11.0
    before = sim.points
    events = run(sim, 0.2)
    assert any(event.kind == "red" for event in events)
    assert sim.points <= before


def test_green_light_gives_bonus() -> None:
    sim = make_sim()
    sim.time = 0.0
    sim.player_abs = 139.0
    sim.player_speed = 11.0
    events = run(sim, 0.2)
    assert any(event.kind == "green" for event in events)
    assert sim.bonus >= 60


def test_collision_costs_a_life_and_grants_invulnerability() -> None:
    sim = make_sim()
    sim.vehicles.append(
        Vehicle(vid=90, kind="auto", x=0.0, y=sim.player_abs, speed=0.0, lane=1)
    )
    run(sim, 1 / 60)
    assert sim.lives == MAX_LIVES - 1
    assert not sim.game_over
    assert sim.invulnerable > 0

    sim.vehicles.append(
        Vehicle(vid=91, kind="auto", x=0.0, y=sim.player_abs, speed=0.0, lane=1)
    )
    run(sim, 0.5)
    assert sim.lives == MAX_LIVES - 1


def test_third_crash_ends_the_run() -> None:
    sim = make_sim()
    sim.lives = 1
    sim.vehicles.append(
        Vehicle(vid=92, kind="moto", x=0.0, y=sim.player_abs, speed=0.0, lane=1)
    )
    run(sim, 1 / 60)
    assert sim.game_over
    assert sim.lives == 0


def test_game_over_freezes_the_simulation() -> None:
    sim = make_sim()
    sim.game_over = True
    position = sim.player_abs
    run(sim, 1.0)
    assert sim.player_abs == position


def test_bus_stops_at_the_corner_then_leaves() -> None:
    sim = make_sim()
    sim.time = 0.0
    stop = bus_stop_y(150.0)
    bus = Vehicle(
        vid=80,
        kind="colectivo",
        x=LANE_X[2],
        y=stop - 22.0,
        speed=VEHICLE_KMH["colectivo"] / 3.6,
        lane=2,
    )
    sim.vehicles.append(bus)
    stopped = False
    for _ in range(60 * 5):
        sim.step(1 / 60, 0.0, False)
        if bus.speed < 0.2 and abs(bus.y - stop) < 3.0:
            stopped = True
    assert stopped
    run(sim, 4.0)
    assert bus.y > stop


def test_bicycle_ignores_the_red_light() -> None:
    sim = make_sim()
    sim.time = 10.0
    bike = Vehicle(
        vid=81,
        kind="bici",
        x=LANE_X[2],
        y=139.0,
        speed=VEHICLE_KMH["bici"] / 3.6,
        lane=2,
        weave_phase=0.0,
    )
    sim.vehicles.append(bike)
    run(sim, 2.0)
    assert bike.y > 150.0 - STOP_LINE_GAP


def test_cross_traffic_spawns_on_red() -> None:
    sim = make_sim()
    sim.time = 10.0
    sim.player_abs = 130.0
    sim._cross_timer = 0.0
    run(sim, 0.4)
    assert any(vehicle.cross for vehicle in sim.vehicles)


def test_cross_traffic_clears_when_the_light_turns_green() -> None:
    sim = make_sim()
    sim.time = 0.0
    sim.player_abs = 120.0
    sim.vehicles.append(
        Vehicle(
            vid=85,
            kind="auto",
            x=20.0,
            y=150.0,
            speed=0.0,
            cross=1,
            cross_speed=8.0,
        )
    )
    run(sim, 1 / 60)
    assert all(vehicle.vid != 85 for vehicle in sim.vehicles)


def test_near_miss_is_rewarded_without_collision() -> None:
    sim = make_sim()
    car = Vehicle(
        vid=82,
        kind="auto",
        x=1.7,
        y=sim.player_abs + 2.0,
        speed=VEHICLE_KMH["auto"] / 3.6,
        lane=1,
    )
    sim.vehicles.append(car)
    events = run(sim, 1 / 60)
    assert any(event.kind == "near" for event in events)
    assert sim.lives == MAX_LIVES


def test_points_never_go_negative() -> None:
    sim = make_sim()
    sim.distance = 5.0
    sim.bonus = -500
    assert sim.points == 0


def test_old_vehicles_are_cleaned_up() -> None:
    sim = make_sim()
    sim.vehicles.append(
        Vehicle(
            vid=83,
            kind="auto",
            x=0.0,
            y=sim.player_abs - 400.0,
            speed=0.0,
            lane=1,
        )
    )
    run(sim, 1 / 60)
    assert all(vehicle.vid != 83 for vehicle in sim.vehicles)


def test_long_run_stays_bounded() -> None:
    sim = make_sim(seed=12)
    sim.invulnerable = 9999.0
    run(sim, 40.0)
    assert len(sim.vehicles) < 20
    for vehicle in sim.vehicles:
        rel = vehicle.y - sim.player_abs
        if vehicle.cross:
            assert abs(vehicle.x) < 45.0
        else:
            assert -90.0 < rel < 340.0


def test_boxes_overlap_and_player_box_is_centred() -> None:
    box = player_box(0.0, 10.0)
    assert box == (-0.42, 0.42, 9.05, 10.95)
    other = (0.0, 1.0, 9.0, 11.0)
    assert overlaps(box, other)
    assert not overlaps(box, (2.0, 3.0, 9.0, 11.0))


def test_cross_vehicle_box_is_rotated() -> None:
    v = Vehicle(vid=84, kind="auto", x=0.0, y=0.0, speed=0.0, cross=1)
    box = vehicle_box(v)
    assert box[1] - box[0] > box[3] - box[2]
