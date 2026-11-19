"""Reglas puras de Patinete No Mueras: jugador, trafico, semaforos y choques.

Este modulo no importa Panda3D: se puede testear con ``pytest`` puro. El mundo
se simula en coordenadas absolutas y la capa visual resta ``player_abs`` para
dibujar en la camara (asi el mundo infinito no acumula error de float).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

KMH_TO_MPS = 1.0 / 3.6
MPS_TO_KMH = 3.6

SCOOTER_MAX_KMH = 40.0
VEHICLE_KMH = {
    "auto": 80.0,
    "taxi": 100.0,
    "colectivo": 60.0,
    "bici": 20.0,
    "moto": 85.0,
}

LANE_X: tuple[float, float, float] = (-3.4, 0.0, 3.4)
LANE_WIDTH = 3.4
ROAD_HALF_WIDTH = 5.2
CURB_X = 4.85
INTERSECTION_SPACING = 150.0
CROSS_HALF_LENGTH = 6.5
STOP_LINE_GAP = 9.5
CYCLE = 21.0
GREEN_TIME = 9.0
YELLOW_TIME = 3.0
RED_TIME = CYCLE - GREEN_TIME - YELLOW_TIME

START_ABS = 40.0
PLAYER_HALF_WIDTH = 0.42
PLAYER_HALF_LENGTH = 0.95
PLAYER_ACCEL = 3.2
PLAYER_BRAKE = 6.0
PLAYER_LATERAL = 4.4

AI_ACCEL = 3.0
AI_BRAKE = 9.5

MAX_LIVES = 3
RED_PENALTY = 120
GREEN_BONUS = 60
NEAR_MISS_BONUS = 25

GREEN = "verde"
YELLOW = "amarillo"
RED = "rojo"


@dataclass(frozen=True, slots=True)
class VehicleSpec:
    length: float
    width: float
    cruise_kmh: float
    height: float


SPECS: dict[str, VehicleSpec] = {
    "auto": VehicleSpec(4.4, 1.85, VEHICLE_KMH["auto"], 1.55),
    "taxi": VehicleSpec(4.6, 1.85, VEHICLE_KMH["taxi"], 1.65),
    "colectivo": VehicleSpec(11.0, 2.55, VEHICLE_KMH["colectivo"], 3.1),
    "bici": VehicleSpec(1.7, 0.65, VEHICLE_KMH["bici"], 1.7),
    "moto": VehicleSpec(2.0, 0.8, VEHICLE_KMH["moto"], 1.65),
}


@dataclass(slots=True)
class Vehicle:
    vid: int
    kind: str
    x: float
    y: float
    speed: float
    lane: int = 1
    target_x: float | None = None
    cross: int = 0
    cross_speed: float = 0.0
    dwell: float = 0.0
    weave_phase: float = 0.0
    near_miss: bool = False
    warned: bool = False
    blink: float = 0.0
    stopped_for: str = ""

    @property
    def spec(self) -> VehicleSpec:
        return SPECS[self.kind]

    @property
    def length(self) -> float:
        return self.spec.length

    @property
    def width(self) -> float:
        return self.spec.width


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    value: int = 0
    side: int = 0


@dataclass(frozen=True, slots=True)
class LightView:
    center: float
    rel_y: float
    state: str
    has_stop: bool = True


def light_state(center: float, time: float) -> str:
    """Color del semaforo en ``center`` en el instante ``time``."""
    index = round(center / INTERSECTION_SPACING)
    phase = (time + index * 4.7) % CYCLE
    if phase < GREEN_TIME:
        return GREEN
    if phase < GREEN_TIME + YELLOW_TIME:
        return YELLOW
    return RED


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _approach(value: float, target: float, rate: float, dt: float) -> float:
    if target > value:
        return min(target, value + rate * dt)
    return max(target, value - rate * dt)


def player_box(x: float, y: float) -> tuple[float, float, float, float]:
    return (
        x - PLAYER_HALF_WIDTH,
        x + PLAYER_HALF_WIDTH,
        y - PLAYER_HALF_LENGTH,
        y + PLAYER_HALF_LENGTH,
    )


def vehicle_box(v: Vehicle) -> tuple[float, float, float, float]:
    if v.cross:
        half_x = v.length / 2.0
        half_y = v.width / 2.0
    else:
        half_x = v.width / 2.0
        half_y = v.length / 2.0
    return (v.x - half_x, v.x + half_x, v.y - half_y, v.y + half_y)


def overlaps(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def bus_stop_y(center: float) -> float:
    return center + CROSS_HALF_LENGTH + 8.0


class TrafficSim:
    """Una avenida de mano unica y tres carriles, con trafico y semaforos."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self._next_vid = 1
        self.reset()

    def reset(self) -> None:
        self.time = 0.0
        self.player_abs = START_ABS
        self.player_x = LANE_X[1]
        self.player_speed = 0.0
        self.lateral = 0.0
        self.lean = 0.0
        self.lives = MAX_LIVES
        self.distance = 0.0
        self.bonus = 0
        self.invulnerable = 0.0
        self.stunned = 0.0
        self.game_over = False
        self.vehicles: list[Vehicle] = []
        self.lights: list[LightView] = []
        self.rear_side = 0
        self._ahead_timer = 0.5
        self._behind_timer = 2.0
        self._cross_timer = 0.9
        self._warn_timer = 0.0
        self._curb_timer = 0.0
        self._last_abs = START_ABS
        self._spawn_initial()
        self._step_lights([])

    # -- estado derivado ----------------------------------------------------

    @property
    def player_speed_kmh(self) -> float:
        return self.player_speed * MPS_TO_KMH

    @property
    def points(self) -> int:
        return max(0, int(self.distance) + self.bonus)

    def light_ahead(self) -> LightView | None:
        for light in self.lights:
            if light.rel_y > -STOP_LINE_GAP - 2.0:
                return light
        return None

    # -- ciclo principal ----------------------------------------------------

    def step(self, dt: float, steer: float, brake: bool) -> list[Event]:
        events: list[Event] = []
        if self.game_over:
            return events
        dt = _clamp(dt, 0.0, 0.1)
        if dt <= 0.0:
            return events

        self.time += dt
        self._last_abs = self.player_abs
        self._step_player(dt, steer, brake, events)
        self._step_lights(events)
        self._step_vehicles(dt, events)
        self._step_cross_traffic(dt)
        self._check_collisions(events)
        self._check_near_miss(events)
        self._check_rear(events, dt)
        self._spawn(dt)
        self._cleanup()
        if self.invulnerable > 0.0:
            self.invulnerable = max(0.0, self.invulnerable - dt)
        if self.stunned > 0.0:
            self.stunned = max(0.0, self.stunned - dt)
        self.distance = max(0.0, self.player_abs - START_ABS)
        return events

    def _step_player(
        self, dt: float, steer: float, brake: bool, events: list[Event]
    ) -> None:
        if self.stunned > 0.0 or brake:
            target = 0.0
        else:
            target = SCOOTER_MAX_KMH * KMH_TO_MPS
        if target > self.player_speed:
            self.player_speed = _approach(
                self.player_speed, target, PLAYER_ACCEL, dt
            )
        else:
            self.player_speed = _approach(
                self.player_speed, target, PLAYER_BRAKE, dt
            )

        target_lateral = _clamp(steer, -1.0, 1.0) * PLAYER_LATERAL
        response = min(1.0, dt * 9.0)
        self.lateral += (target_lateral - self.lateral) * response
        self.lean = self.lateral / PLAYER_LATERAL
        new_x = self.player_x + self.lateral * dt

        if new_x < -CURB_X or new_x > CURB_X:
            self.player_x = _clamp(new_x, -CURB_X, CURB_X)
            if abs(self.lateral) > 1.0 and self._curb_timer <= 0.0:
                self._curb_timer = 0.9
                self.player_speed *= 0.985
                events.append(Event("curb", side=-1 if self.player_x < 0 else 1))
        else:
            self.player_x = new_x
        self._curb_timer = max(0.0, self._curb_timer - dt)

        self.player_abs += self.player_speed * dt

    def _step_lights(self, events: list[Event]) -> None:
        first = math.floor(self.player_abs / INTERSECTION_SPACING)
        self.lights = []
        for index in range(first - 1, first + 4):
            center = index * INTERSECTION_SPACING
            state = light_state(center, self.time)
            self.lights.append(
                LightView(center, center - self.player_abs, state)
            )
            line = center - STOP_LINE_GAP
            if self._last_abs < line <= self.player_abs:
                if state == RED:
                    self.bonus -= RED_PENALTY
                    events.append(Event("red", value=-RED_PENALTY))
                elif state == GREEN:
                    self.bonus += GREEN_BONUS
                    events.append(Event("green", value=GREEN_BONUS))
                else:
                    events.append(Event("yellow"))

    def _step_vehicles(self, dt: float, events: list[Event]) -> None:
        for v in self.vehicles:
            if v.cross:
                v.x += v.cross * v.cross_speed * dt
                continue
            self._steer_vehicle(v, dt, events)
            desired = self._desired_speed(v)
            if v.dwell > 0.0:
                desired = 0.0
                v.dwell = max(0.0, v.dwell - dt)
            accel = AI_ACCEL if desired > v.speed else AI_BRAKE
            v.speed = _approach(v.speed, desired, accel, dt)
            v.y += v.speed * dt
            v.blink = max(0.0, v.blink - dt)

        self._resolve_overlaps()

    def _steer_vehicle(
        self, v: Vehicle, dt: float, events: list[Event]
    ) -> None:
        if v.target_x is not None:
            delta = v.target_x - v.x
            step = 3.2 * dt
            if abs(delta) <= step:
                v.x = v.target_x
                v.target_x = None
            else:
                v.x += math.copysign(step, delta)
            return

        if v.kind == "bici":
            base = LANE_X[v.lane]
            v.weave_phase += dt * 0.9
            v.x = _clamp(base + math.sin(v.weave_phase) * 2.2, -4.5, 4.5)
            return

        if v.kind == "moto":
            phase = v.weave_phase
            v.weave_phase += dt * 2.2
            v.x += (math.sin(v.weave_phase) - math.sin(phase)) * 0.12
            return

        if v.kind in ("taxi", "auto"):
            if self._lane_blocked(v) and v.blink <= 0.0:
                self._taxi_change_lane(v, cooldown=1.0 if v.kind == "taxi" else 2.4)
            return

        if v.kind == "colectivo":
            stop = self._next_bus_stop(v)
            distance = stop - v.y
            if 0.0 < distance < 80.0 and abs(v.x - LANE_X[2]) > 0.4:
                v.target_x = LANE_X[2]
                v.blink = 1.2
                if (
                    not v.warned
                    and abs(self.player_abs - v.y) < 45.0
                    and self.player_x > 0.6
                ):
                    v.warned = True
                    events.append(Event("bus", side=1))

    def _lane_blocked(self, v: Vehicle) -> bool:
        if v.speed < 1.0:
            return False
        for other in self.vehicles:
            if other is v or other.cross:
                continue
            if abs(other.x - v.x) > 2.0:
                continue
            gap = other.y - v.y - (other.length + v.length) / 2.0
            if 0.0 < gap < 30.0 and other.speed < v.speed * 0.72:
                return True
        gap_player = self.player_abs - v.y - v.length / 2.0
        return 0.0 < gap_player < 26.0 and self.player_speed < v.speed * 0.72

    def _taxi_change_lane(self, v: Vehicle, *, cooldown: float = 1.0) -> None:
        for lane in (v.lane - 1, v.lane + 1):
            if 0 <= lane <= 2 and self._lane_free(lane, v.y, 20.0, ignore=v):
                v.target_x = LANE_X[lane]
                v.lane = lane
                v.blink = cooldown
                return

    def _desired_speed(self, v: Vehicle) -> float:
        desired = v.spec.cruise_kmh * KMH_TO_MPS
        if v.kind in ("auto", "taxi", "colectivo"):
            light = self._light_block(v)
            if light is not None:
                desired = min(desired, light)
            if v.kind == "colectivo":
                desired = min(desired, self._bus_stop_speed(v))
            gap, leader_speed = self._leader_gap(v)
            if gap < 30.0:
                safe = leader_speed + max(0.0, gap - 7.0) * 0.9
                desired = min(desired, max(0.0, safe))
        return max(0.0, desired)

    def _light_block(self, v: Vehicle) -> float | None:
        for index in range(
            int(v.y // INTERSECTION_SPACING) - 1,
            int(v.y // INTERSECTION_SPACING) + 2,
        ):
            center = index * INTERSECTION_SPACING
            line = center - STOP_LINE_GAP
            distance = line - v.y
            if not (0.0 < distance < 90.0):
                continue
            state = light_state(center, self.time)
            if state == RED:
                return max(0.0, (distance - 2.0) * 0.55)
            if state == YELLOW and distance > 12.0:
                return max(0.0, (distance - 2.0) * 0.7)
        return None

    def _bus_stop_speed(self, v: Vehicle) -> float:
        stop = self._next_bus_stop(v)
        distance = stop - v.y
        key = f"{int(stop)}"
        if 0.0 < distance < 30.0 and abs(v.x - LANE_X[2]) < 1.2:
            if distance < 2.0:
                if v.stopped_for != key:
                    if v.dwell <= 0.0:
                        v.dwell = 2.4
                        v.stopped_for = key
                    return 0.0
                return v.spec.cruise_kmh * KMH_TO_MPS
            return max(0.0, (distance - 1.0) * 0.9)
        return v.spec.cruise_kmh * KMH_TO_MPS

    def _next_bus_stop(self, v: Vehicle) -> float:
        index = int(v.y // INTERSECTION_SPACING)
        candidate = bus_stop_y(index * INTERSECTION_SPACING)
        if v.y > candidate + 1.0:
            index += 1
        return bus_stop_y(index * INTERSECTION_SPACING)

    def _leader_gap(self, v: Vehicle) -> tuple[float, float]:
        best_gap = 1e9
        best_speed = 0.0
        for other in self.vehicles:
            if other is v or other.cross:
                continue
            if abs(other.x - v.x) > (other.width + v.width) / 2.0 + 0.3:
                continue
            gap = other.y - v.y - (other.length + v.length) / 2.0
            if 0.0 < gap < best_gap:
                best_gap = gap
                best_speed = other.speed
        if abs(self.player_x - v.x) < v.width / 2.0 + 0.7:
            gap = self.player_abs - v.y - v.length / 2.0
            if 0.0 < gap < best_gap:
                best_gap = gap
                best_speed = self.player_speed
        return best_gap, best_speed

    def _resolve_overlaps(self) -> None:
        ordered = sorted(
            (v for v in self.vehicles if not v.cross),
            key=lambda v: v.y,
            reverse=True,
        )
        for index, v in enumerate(ordered):
            for other in ordered[index + 1 :]:
                if abs(other.x - v.x) > (v.width + other.width) / 2.0:
                    continue
                gap = v.y - other.y - (v.length + other.length) / 2.0
                if 0.0 < gap < 0.4:
                    other.y = v.y - (v.length + other.length) / 2.0 - 0.45
                    other.speed = min(other.speed, v.speed)

    def _step_cross_traffic(self, dt: float) -> None:
        for v in list(self.vehicles):
            if not v.cross:
                continue
            center = round(v.y / INTERSECTION_SPACING) * INTERSECTION_SPACING
            if light_state(center, self.time) != RED and abs(v.x) > 7.0:
                self.vehicles.remove(v)

        first = math.floor(self.player_abs / INTERSECTION_SPACING)
        candidates: list[LightView] = []
        for index in range(first, first + 2):
            center = index * INTERSECTION_SPACING
            rel = center - self.player_abs
            if not (-12.0 < rel < 115.0):
                continue
            if light_state(center, self.time) != RED:
                continue
            index_phase = (self.time + index * 4.7) % CYCLE
            if CYCLE - index_phase < 3.0:
                continue
            candidates.append(LightView(center, rel, RED))
        if not candidates:
            self._cross_timer = 0.5
            return
        self._cross_timer -= dt
        if self._cross_timer > 0.0:
            return
        if sum(1 for v in self.vehicles if v.cross) >= 4:
            return
        target = candidates[0]
        direction = 1 if self.rng.random() < 0.5 else -1
        kind = "bici" if self.rng.random() < 0.22 else "auto"
        speed = 5.5 + self.rng.random() * 4.0
        if kind == "bici":
            speed = VEHICLE_KMH["bici"] * KMH_TO_MPS
        y = target.center + (2.6 if direction > 0 else -2.6)
        if kind == "bici":
            direction = 1
            y = target.center + 5.4
        self.vehicles.append(
            Vehicle(
                vid=self._next_vid,
                kind=kind,
                x=-38.0 * direction,
                y=y,
                speed=0.0,
                cross=direction,
                cross_speed=speed,
                lane=-1,
            )
        )
        self._next_vid += 1
        self._cross_timer = 1.1 + self.rng.random() * 0.9

    def _check_collisions(self, events: list[Event]) -> None:
        if self.invulnerable > 0.0 or self.game_over:
            return
        player = player_box(self.player_x, self.player_abs)
        for v in list(self.vehicles):
            if not overlaps(player, vehicle_box(v)):
                continue
            self.vehicles.remove(v)
            self.lives -= 1
            self.player_speed = 0.0
            self.lateral = 0.0
            self.invulnerable = 2.4
            self.stunned = 1.1
            events.append(Event("crash", side=-1 if v.x < self.player_x else 1))
            if self.lives <= 0:
                self.lives = 0
                self.game_over = True
            return

    def _check_near_miss(self, events: list[Event]) -> None:
        if self.invulnerable > 0.0 or self.game_over:
            return
        for v in self.vehicles:
            if v.cross or v.near_miss:
                continue
            rel = self.player_abs - v.y
            lateral = abs(v.x - self.player_x) - (v.width / 2.0 + PLAYER_HALF_WIDTH)
            close = abs(rel) < v.length / 2.0 + PLAYER_HALF_LENGTH + 0.8
            if close and 0.0 <= lateral < 0.55:
                v.near_miss = True
                self.bonus += NEAR_MISS_BONUS
                events.append(Event("near", value=NEAR_MISS_BONUS))

    def _check_rear(self, events: list[Event], dt: float) -> None:
        self._warn_timer = max(0.0, self._warn_timer - dt)
        closest: Vehicle | None = None
        closest_rel = -1e9
        for v in self.vehicles:
            if v.cross:
                continue
            rel = v.y - self.player_abs
            if not (-55.0 < rel < -5.0):
                continue
            if v.speed - self.player_speed < 2.0:
                continue
            if rel > closest_rel:
                closest = v
                closest_rel = rel
        if closest is None:
            self.rear_side = 0
            return
        side = 1 if closest.x > self.player_x + 0.3 else -1
        self.rear_side = side
        if self._warn_timer <= 0.0:
            self._warn_timer = 2.4
            events.append(Event("rear", side=side))

    def _spawn(self, dt: float) -> None:
        self._ahead_timer -= dt
        if self._ahead_timer <= 0.0:
            self._ahead_timer = 0.75 + self.rng.random() * 1.15
            self._spawn_ahead()
        self._behind_timer -= dt
        if self._behind_timer <= 0.0:
            self._behind_timer = 2.4 + self.rng.random() * 1.8
            self._spawn_behind()

    def _spawn_ahead(self) -> None:
        ahead = [
            v
            for v in self.vehicles
            if not v.cross and v.y - self.player_abs > 0.0
        ]
        if len(ahead) >= 9:
            return
        lane = self.rng.choices((0, 1, 2), weights=(30, 35, 35))[0]
        if lane == 2:
            kind = self.rng.choices(
                ("colectivo", "auto", "bici"), weights=(38, 32, 30)
            )[0]
        elif lane == 0:
            kind = self.rng.choices(("auto", "taxi", "moto"), weights=(50, 32, 18))[0]
        else:
            kind = self.rng.choices(
                ("auto", "taxi", "colectivo", "bici"), weights=(45, 20, 20, 15)
            )[0]
        if kind == "bici" and sum(1 for v in ahead if v.kind == "bici") >= 3:
            kind = "auto"
        y = self.player_abs + 175.0 + self.rng.random() * 95.0
        x = LANE_X[lane]
        if kind == "moto":
            x = LANE_X[lane] + self.rng.choice((-1.7, 1.7))
        if not self._spot_free(x, y, 20.0) or self._near_intersection(y, 14.0):
            return
        self.vehicles.append(
            Vehicle(
                vid=self._next_vid,
                kind=kind,
                x=x,
                y=y,
                speed=min(
                    self.rng.uniform(0.7, 1.0) * SPECS[kind].cruise_kmh * KMH_TO_MPS,
                    SPECS[kind].cruise_kmh * KMH_TO_MPS,
                ),
                lane=lane,
            )
        )
        self._next_vid += 1

    def _spawn_behind(self) -> None:
        behind = [
            v
            for v in self.vehicles
            if not v.cross and v.y - self.player_abs < -4.0
        ]
        if len(behind) >= 2:
            return
        y = self.player_abs - 42.0 - self.rng.random() * 34.0
        roll = self.rng.random()
        if roll < 0.5:
            x = self.rng.choice((-1.75, 1.75, -5.0, 5.0)) + self.rng.uniform(-0.3, 0.3)
            kind = "moto"
            speed = VEHICLE_KMH["moto"] * KMH_TO_MPS
            lane = -1
        elif roll < 0.75:
            lane = self.rng.choice((0, 1))
            x = LANE_X[lane]
            kind = "taxi"
            speed = VEHICLE_KMH["taxi"] * KMH_TO_MPS
        else:
            player_lane = min(
                range(3), key=lambda index: abs(LANE_X[index] - self.player_x)
            )
            options = [index for index in range(3) if index != player_lane]
            lane = self.rng.choice(options)
            x = LANE_X[lane]
            kind = "auto"
            speed = VEHICLE_KMH["auto"] * KMH_TO_MPS
        if not self._spot_free(x, y, 12.0):
            return
        self.vehicles.append(
            Vehicle(
                vid=self._next_vid,
                kind=kind,
                x=x,
                y=y,
                speed=speed,
                lane=lane,
            )
        )
        self._next_vid += 1

    def _spawn_initial(self) -> None:
        plan = (
            ("auto", 0, 120.0),
            ("auto", 1, 165.0),
            ("colectivo", 2, 105.0),
            ("bici", 2, 70.0),
            ("taxi", 0, 55.0),
            ("auto", 1, 240.0),
        )
        for kind, lane, rel in plan:
            speed = SPECS[kind].cruise_kmh * KMH_TO_MPS * 0.85
            self.vehicles.append(
                Vehicle(
                    vid=self._next_vid,
                    kind=kind,
                    x=LANE_X[lane],
                    y=START_ABS + rel,
                    speed=speed,
                    lane=lane,
                    weave_phase=lane,
                )
            )
            self._next_vid += 1

    def _spot_free(self, x: float, y: float, margin: float) -> bool:
        for v in self.vehicles:
            if v.cross:
                continue
            if abs(v.x - x) < 2.2 and abs(v.y - y) < margin:
                return False
        return True

    def _lane_free(
        self, lane: int, y: float, margin: float, ignore: Vehicle
    ) -> bool:
        for v in self.vehicles:
            if v is ignore or v.cross:
                continue
            if abs(v.x - LANE_X[lane]) < 2.0 and abs(v.y - y) < margin:
                return False
        player_gap = self.player_abs - y
        return not (
            abs(self.player_x - LANE_X[lane]) < 1.6
            and -12.0 < player_gap < 20.0
        )

    def _near_intersection(self, y: float, margin: float) -> bool:
        index = round(y / INTERSECTION_SPACING)
        return abs(y - index * INTERSECTION_SPACING) < margin

    def _cleanup(self) -> None:
        keep: list[Vehicle] = []
        for v in self.vehicles:
            rel = v.y - self.player_abs
            if v.cross:
                if abs(v.x) < 42.0:
                    keep.append(v)
            elif -75.0 < rel < 330.0:
                keep.append(v)
        self.vehicles = keep
