"""Escena 3D de la avenida en POV: calle, edificios, semaforos y trafico."""

from __future__ import annotations

import random
from typing import Any

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Fog,
    NodePath,
    Vec4,
)

from .sim import LANE_X, LightView, TrafficSim, Vehicle

ASPHALT = Vec4(0.085, 0.095, 0.125, 1.0)
CROSS_ASPHALT = Vec4(0.075, 0.085, 0.11, 1.0)
PAINT = Vec4(0.72, 0.74, 0.78, 1.0)
PAINT_WARM = Vec4(0.78, 0.68, 0.42, 1.0)
SIDEWALK = Vec4(0.135, 0.145, 0.185, 1.0)
CURB = Vec4(0.34, 0.36, 0.40, 1.0)
CONCRETE = Vec4(0.24, 0.25, 0.30, 1.0)
STEEL = Vec4(0.18, 0.20, 0.24, 1.0)
DARK = Vec4(0.035, 0.04, 0.055, 1.0)
GLASS = Vec4(0.10, 0.20, 0.30, 1.0)
WINDOW_WARM = Vec4(1.0, 0.78, 0.42, 1.0)
WINDOW_COOL = Vec4(0.55, 0.78, 1.0, 1.0)
LAMP_WARM = Vec4(1.0, 0.86, 0.55, 1.0)
TAIL_RED = Vec4(1.0, 0.12, 0.10, 1.0)
HEAD_LIGHT = Vec4(1.0, 0.95, 0.78, 1.0)
LAMP_OFF = Vec4(0.10, 0.10, 0.11, 1.0)
SIGNAL_ON = {
    "rojo": Vec4(1.0, 0.12, 0.10, 1.0),
    "amarillo": Vec4(1.0, 0.72, 0.12, 1.0),
    "verde": Vec4(0.15, 1.0, 0.45, 1.0),
}
FOG_COLOR = Vec4(0.035, 0.05, 0.085, 1.0)
SPAN = 320.0
AHEAD = 240.0

CAR_COLORS = (
    Vec4(0.70, 0.16, 0.18, 1.0),
    Vec4(0.30, 0.42, 0.66, 1.0),
    Vec4(0.62, 0.64, 0.68, 1.0),
    Vec4(0.18, 0.46, 0.42, 1.0),
    Vec4(0.50, 0.32, 0.66, 1.0),
    Vec4(0.82, 0.52, 0.16, 1.0),
)
TAXI_COLOR = Vec4(0.98, 0.72, 0.10, 1.0)
BUS_COLORS = (
    Vec4(0.66, 0.14, 0.16, 1.0),
    Vec4(0.16, 0.42, 0.36, 1.0),
    Vec4(0.30, 0.34, 0.52, 1.0),
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _wrap(y: float) -> float:
    """Envuelve una posicion absoluta en la ventana visible del jugador."""
    value = y % SPAN
    if value > AHEAD:
        value -= SPAN
    return value


class StreetScene:
    """Construye y anima la avenida. Todo cuelga de ``ctx.scene``."""

    def __init__(self, base: Any, root: NodePath) -> None:
        self.base = base
        self.root = root
        self.rng = random.Random(7)
        self.world = root.attach_new_node("street")
        self.dynamic = root.attach_new_node("traffic")
        self.props: list[tuple[NodePath, float, str]] = []
        self.intersections: list[NodePath] = []
        self.signal_lamps: list[list[NodePath]] = []
        self.signal_states: list[str] = []
        self.vehicle_nodes: dict[int, NodePath] = {}
        self._build_lights()
        self._build_road()
        self._build_buildings()
        self._build_sidewalks()
        self._build_streetlights()
        self._build_dashes()
        self._build_intersections()
        self.pov = self._build_scooter()

    # -- construccion -------------------------------------------------------

    def _box(
        self,
        parent: NodePath,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        color: Vec4,
        *,
        lit: bool = False,
    ) -> NodePath:
        model = self.base.loader.loadModel("models/box")
        model.set_texture_off(1)
        model.set_scale(*size)
        model.set_pos(
            center[0] - size[0] / 2.0,
            center[1] - size[1] / 2.0,
            center[2] - size[2] / 2.0,
        )
        model.set_color(color)
        if lit:
            model.set_light_off(1)
        model.reparent_to(parent)
        return model

    def _sphere(
        self,
        parent: NodePath,
        center: tuple[float, float, float],
        radius: float,
        color: Vec4,
        *,
        lit: bool = False,
    ) -> NodePath:
        model = self.base.loader.loadModel("models/misc/sphere")
        model.set_texture_off(1)
        model.set_scale(radius)
        model.set_pos(*center)
        model.set_color(color)
        if lit:
            model.set_light_off(1)
        model.reparent_to(parent)
        return model

    def _build_lights(self) -> None:
        ambient = AmbientLight("street-ambient")
        ambient.set_color(Vec4(0.85, 0.88, 1.0, 1.0))
        self.root.set_light(self.root.attach_new_node(ambient))

        key = DirectionalLight("street-key")
        key.set_color(Vec4(0.55, 0.62, 0.85, 1.0))
        node = self.root.attach_new_node(key)
        node.set_hpr(25.0, -40.0, 0.0)
        self.root.set_light(node)

        fog = Fog("street-fog")
        fog.set_color(FOG_COLOR)
        fog.set_linear_range(55.0, 235.0)
        self.root.set_fog(fog)

    def _build_road(self) -> None:
        self._box(
            self.world,
            (0.0, 120.0, -0.09),
            (90.0, 460.0, 0.1),
            Vec4(0.055, 0.065, 0.09, 1.0),
        )
        self._box(self.world, (0.0, 120.0, -0.06), (10.4, 440.0, 0.12), ASPHALT)
        for side in (-1.0, 1.0):
            self._box(
                self.world,
                (side * 5.14, 120.0, 0.012),
                (0.12, 440.0, 0.02),
                PAINT,
            )

    def _build_buildings(self) -> None:
        spacing = 22.0
        for side in (-1.0, 1.0):
            for index in range(14):
                height = 7.0 + self.rng.random() * 27.0
                length = 12.0 + self.rng.random() * 7.0
                depth = 8.0 + self.rng.random() * 6.0
                x = side * (10.8 + depth / 2.0)
                node = self.world.attach_new_node(f"building-{side}-{index}")
                shade = 0.10 + self.rng.random() * 0.10
                body = Vec4(shade * 0.8, shade * 0.9, shade * 1.4, 1.0)
                self._box(
                    node,
                    (x, 0.0, height / 2.0),
                    (depth, length, height),
                    body,
                )
                self._box(
                    node,
                    (x, 0.0, height + 0.35),
                    (depth * 0.5, length * 0.4, 0.7),
                    DARK,
                )
                for band in range(2):
                    if self.rng.random() < 0.3:
                        continue
                    lit = (
                        WINDOW_WARM
                        if self.rng.random() < 0.62
                        else WINDOW_COOL
                    )
                    z = 2.2 + self.rng.random() * max(1.0, height - 4.0)
                    offset = (band - 0.5) * length * 0.3
                    self._box(
                        node,
                        (x - side * (depth / 2.0 + 0.02), offset, z),
                        (0.05, length * 0.42, 0.45),
                        lit,
                        lit=True,
                    )
                abs_y = index * spacing + spacing / 2.0
                self.props.append((node, abs_y, "building"))

    def _build_sidewalks(self) -> None:
        for side in (-1.0, 1.0):
            for index in range(20):
                node = self.world.attach_new_node(f"sidewalk-{side}-{index}")
                self._box(
                    node,
                    (side * 7.85, 0.0, 0.11),
                    (5.4, 16.0, 0.22),
                    SIDEWALK,
                )
                self._box(
                    node,
                    (side * 5.25, 0.0, 0.14),
                    (0.3, 16.0, 0.28),
                    CURB,
                )
                self.props.append((node, index * 16.0 + 8.0, "sidewalk"))

    def _build_streetlights(self) -> None:
        for side in (-1.0, 1.0):
            for index in range(10):
                node = self.world.attach_new_node(f"lamp-{side}-{index}")
                x = side * 8.6
                self._box(node, (x, 0.0, 3.1), (0.12, 0.12, 6.2), STEEL)
                self._box(
                    node,
                    (x - side * 1.15, 0.0, 6.15),
                    (2.4, 0.10, 0.10),
                    STEEL,
                )
                self._sphere(
                    node, (x - side * 2.2, 0.0, 6.0), 0.24, LAMP_WARM, lit=True
                )
                glow = self._sphere(
                    node, (x - side * 2.2, 0.0, 6.0), 0.52, Vec4(1.0, 0.8, 0.4, 0.22)
                )
                glow.set_transparency(1)
                self.props.append((node, index * 32.0 + 8.0, "lamp"))

    def _build_dashes(self) -> None:
        for boundary in (-1.7, 1.7):
            for index in range(40):
                node = self.world.attach_new_node(
                    f"dash-{boundary}-{index}"
                )
                self._box(
                    node,
                    (boundary, 0.0, 0.008),
                    (0.11, 2.6, 0.02),
                    PAINT_WARM,
                )
                self.props.append(
                    (node, index * 8.0, "dash")
                )

    def _build_intersections(self) -> None:
        for slot in range(4):
            node = self.world.attach_new_node(f"intersection-{slot}")
            self._box(
                node,
                (0.0, 0.0, 0.02),
                (120.0, 13.0, 0.03),
                CROSS_ASPHALT,
            )
            for step in range(9):
                x = -4.8 + step * 1.2
                self._box(node, (x, -8.4, 0.03), (0.62, 2.4, 0.02), PAINT)
                self._box(node, (x, 8.4, 0.03), (0.62, 2.4, 0.02), PAINT)
            self._box(node, (0.0, -9.5, 0.03), (10.4, 0.35, 0.02), PAINT)

            for side in (-1.0, 1.0):
                pole_x = side * 6.3
                self._box(node, (pole_x, 0.0, 2.8), (0.16, 0.16, 5.6), STEEL)
            self._box(node, (0.0, 0.0, 5.55), (13.0, 0.14, 0.14), STEEL)

            lamps: list[NodePath] = []
            for lane_x in LANE_X:
                self._build_signal_head(node, lane_x, 5.15, lamps)
            self._build_signal_head(node, 6.3, 3.45, lamps)
            self.signal_lamps.append(lamps)
            self.signal_states.append("")

            self._box(node, (6.9, 14.0, 1.6), (0.1, 0.1, 3.2), STEEL)
            self._box(node, (6.9, 14.0, 3.1), (1.3, 0.08, 0.7), Vec4(0.1, 0.35, 0.6, 1.0))
            self._build_person(node, 7.4, 15.2, Vec4(0.85, 0.45, 0.3, 1.0))
            self._build_person(node, 8.2, 13.4, Vec4(0.4, 0.65, 0.85, 1.0))

            self.intersections.append(node)

    def _build_signal_head(
        self, parent: NodePath, x: float, z: float, lamps: list[NodePath]
    ) -> None:
        self._box(parent, (x, 0.0, z), (0.62, 0.4, 1.9), DARK)
        for offset in (0.62, 0.0, -0.62):
            lamps.append(
                self._sphere(
                    parent,
                    (x, -0.22, z + offset),
                    0.2,
                    LAMP_OFF,
                    lit=True,
                )
            )

    def _build_person(
        self, parent: NodePath, x: float, y: float, jacket: Vec4
    ) -> None:
        self._box(parent, (x, y, 0.85), (0.34, 0.26, 0.95), jacket)
        self._sphere(parent, (x, y, 1.46), 0.16, Vec4(0.78, 0.6, 0.45, 1.0))
        self._box(parent, (x, y, 0.28), (0.3, 0.24, 0.55), Vec4(0.12, 0.13, 0.18, 1.0))

    def _build_scooter(self) -> NodePath:
        pov = self.root.attach_new_node("scooter-pov")
        self._box(pov, (0.0, 0.0, 0.19), (0.05, 0.05, 0.38), STEEL)
        self._box(pov, (0.0, 0.0, 0.38), (0.66, 0.05, 0.05), STEEL)
        for side in (-1.0, 1.0):
            self._box(
                pov,
                (side * 0.33, 0.0, 0.38),
                (0.11, 0.075, 0.075),
                Vec4(0.06, 0.07, 0.09, 1.0),
            )
            self._sphere(
                pov,
                (side * 0.33, -0.02, 0.38),
                0.028,
                Vec4(0.95, 0.35, 0.25, 1.0),
                lit=True,
            )
        pov.set_pos(0.0, 1.2, 0.78)
        return pov

    # -- actualizacion ------------------------------------------------------

    def update(self, sim: TrafficSim, steer: float, look_back: float) -> None:
        self._update_intersections(sim.lights)
        self._update_props(sim)
        self._update_vehicles(sim.vehicles, sim.player_abs)
        self.pov.set_x(sim.player_x)
        self.pov.set_hpr(-steer * 16.0, 0.0, -steer * 5.0)
        if look_back > 0.55:
            self.pov.hide()
        else:
            self.pov.show()

    def _update_props(self, sim: TrafficSim) -> None:
        centers = [light.rel_y for light in sim.lights]
        for node, abs_y, kind in self.props:
            rel = _wrap(abs_y - sim.player_abs)
            node.set_y(rel)
            hidden = False
            if kind in ("building", "sidewalk"):
                hidden = any(abs(rel - center) < 17.0 for center in centers)
            elif kind == "dash":
                hidden = any(abs(rel - center) < 10.0 for center in centers)
            if hidden:
                node.hide()
            else:
                node.show()

    def _update_intersections(self, lights: list[LightView]) -> None:
        visible = [light for light in lights if -140.0 < light.rel_y < 340.0]
        visible.sort(key=lambda light: light.rel_y)
        for slot, node in enumerate(self.intersections):
            if slot >= len(visible):
                node.hide()
                continue
            light = visible[slot]
            node.show()
            node.set_y(light.rel_y)
            self._apply_signal(slot, light.state)

    def _apply_signal(self, slot: int, state: str) -> None:
        if self.signal_states[slot] == state:
            return
        self.signal_states[slot] = state
        lamps = self.signal_lamps[slot]
        for index, lamp in enumerate(lamps):
            color_name = ("rojo", "amarillo", "verde")[index % 3]
            if color_name == state:
                lamp.set_color(SIGNAL_ON[color_name])
            else:
                lamp.set_color(LAMP_OFF)

    def _update_vehicles(self, vehicles: list[Vehicle], player_abs: float) -> None:
        seen: set[int] = set()
        for v in vehicles:
            seen.add(v.vid)
            node = self.vehicle_nodes.get(v.vid)
            if node is None:
                node = self._build_vehicle(v)
                self.vehicle_nodes[v.vid] = node
            node.set_x(v.x)
            node.set_y(v.y - player_abs)
            if v.cross > 0:
                node.set_h(-90.0)
            elif v.cross < 0:
                node.set_h(90.0)
            else:
                node.set_h(0.0)
        for vid in list(self.vehicle_nodes):
            if vid in seen:
                continue
            self.vehicle_nodes.pop(vid).remove_node()

    # -- vehiculos ----------------------------------------------------------

    def _build_vehicle(self, v: Vehicle) -> NodePath:
        node = self.dynamic.attach_new_node(f"{v.kind}-{v.vid}")
        if v.kind == "auto":
            self._build_car(node, CAR_COLORS[v.vid % len(CAR_COLORS)], taxi=False)
        elif v.kind == "taxi":
            self._build_car(node, TAXI_COLOR, taxi=True)
        elif v.kind == "colectivo":
            self._build_bus(node, BUS_COLORS[v.vid % len(BUS_COLORS)])
        elif v.kind == "bici":
            self._build_bike(node, v.vid % 2)
        else:
            self._build_moto(node)
        return node

    def _wheels(
        self, node: NodePath, width: float, length: float, radius: float
    ) -> None:
        for side in (-1.0, 1.0):
            for front in (-1.0, 1.0):
                x = side * (width / 2.0 - 0.02)
                y = front * (length / 2.0 - radius - 0.1)
                self._sphere(node, (x, y, radius), radius, DARK).set_scale(
                    radius * 0.45, radius, radius
                )

    def _build_car(self, node: NodePath, body: Vec4, *, taxi: bool) -> None:
        length, width = 4.4, 1.85
        self._box(node, (0.0, 0.0, 0.62), (width, length, 0.66), body)
        self._box(
            node,
            (0.0, -0.15, 1.12),
            (width - 0.22, length * 0.5, 0.52),
            Vec4(body.x * 0.7, body.y * 0.7, body.z * 0.7, 1.0),
        )
        self._box(node, (0.0, -0.05, 1.14), (width - 0.32, length * 0.36, 0.34), GLASS)
        self._wheels(node, width, length, 0.34)
        for side in (-1.0, 1.0):
            self._box(
                node,
                (side * width * 0.32, length / 2.0 + 0.01, 0.68),
                (0.34, 0.04, 0.16),
                HEAD_LIGHT,
                lit=True,
            )
            self._box(
                node,
                (side * width * 0.32, -length / 2.0 - 0.01, 0.72),
                (0.36, 0.04, 0.16),
                TAIL_RED,
                lit=True,
            )
        if taxi:
            self._box(node, (0.0, -0.1, 1.48), (0.7, 0.3, 0.2), LAMP_WARM, lit=True)

    def _build_bus(self, node: NodePath, body: Vec4) -> None:
        length, width, height = 11.0, 2.55, 2.75
        self._box(node, (0.0, 0.0, height / 2.0 + 0.35), (width, length, height), body)
        self._box(
            node,
            (0.0, -0.4, 1.95),
            (width + 0.02, length - 0.6, 0.78),
            Vec4(0.10, 0.20, 0.27, 1.0),
            lit=True,
        )
        self._box(
            node,
            (0.0, 0.0, height + 0.55),
            (width - 0.4, length - 1.0, 0.4),
            Vec4(0.22, 0.24, 0.28, 1.0),
        )
        self._box(
            node,
            (0.0, -length / 2.0 - 0.02, 2.9),
            (1.4, 0.04, 0.5),
            LAMP_WARM,
            lit=True,
        )
        for side in (-1.0, 1.0):
            self._box(
                node,
                (side * width * 0.3, -length / 2.0 - 0.03, 0.9),
                (0.4, 0.04, 0.22),
                TAIL_RED,
                lit=True,
            )
            self._box(
                node,
                (side * width * 0.32, length / 2.0 + 0.01, 0.95),
                (0.42, 0.04, 0.2),
                HEAD_LIGHT,
                lit=True,
            )
        self._wheels(node, width, length, 0.5)

    def _build_bike(self, node: NodePath, variant: int) -> None:
        jacket = (
            Vec4(0.9, 0.42, 0.2, 1.0)
            if variant == 0
            else Vec4(0.3, 0.7, 0.9, 1.0)
        )
        self._sphere(node, (0.0, -0.55, 0.34), 0.34, DARK).set_scale(0.06, 0.34, 0.34)
        self._sphere(node, (0.0, 0.55, 0.34), 0.34, DARK).set_scale(0.06, 0.34, 0.34)
        self._box(node, (0.0, 0.0, 0.55), (0.07, 1.0, 0.07), STEEL)
        self._box(node, (0.0, 0.0, 0.85), (0.3, 0.24, 0.5), jacket)
        self._sphere(node, (0.0, 0.02, 1.24), 0.14, Vec4(0.85, 0.7, 0.5, 1.0))
        self._box(node, (0.0, 0.6, 0.82), (0.24, 0.2, 0.24), Vec4(0.1, 0.1, 0.12, 1.0))
        self._box(
            node, (0.0, -0.62, 0.62), (0.16, 0.04, 0.1), TAIL_RED, lit=True
        )

    def _build_moto(self, node: NodePath) -> None:
        self._sphere(node, (0.0, -0.62, 0.32), 0.32, DARK).set_scale(0.07, 0.32, 0.32)
        self._sphere(node, (0.0, 0.62, 0.32), 0.32, DARK).set_scale(0.07, 0.32, 0.32)
        self._box(node, (0.0, 0.0, 0.58), (0.34, 1.3, 0.34), Vec4(0.16, 0.18, 0.22, 1.0))
        self._box(node, (0.0, 0.0, 0.95), (0.38, 0.3, 0.52), Vec4(0.1, 0.12, 0.16, 1.0))
        self._sphere(node, (0.0, 0.0, 1.32), 0.16, Vec4(0.95, 0.55, 0.15, 1.0))
        self._sphere(
            node, (0.0, 0.68, 0.72), 0.1, HEAD_LIGHT, lit=True
        )
        self._box(node, (0.0, -0.68, 0.72), (0.16, 0.04, 0.1), TAIL_RED, lit=True)

    # -- limpieza -----------------------------------------------------------

    def destroy(self) -> None:
        for node in self.vehicle_nodes.values():
            node.remove_node()
        self.vehicle_nodes.clear()
        self.world.remove_node()
        self.dynamic.remove_node()
