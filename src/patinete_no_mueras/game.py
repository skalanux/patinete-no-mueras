"""Patinete No Mueras: POV en una avenida, semaforos y trafico vivo."""

from __future__ import annotations

import math
from typing import Any

from toxinator.api import GameContext, GameManifest

from .controls import ControlReader, Controls
from .hud import AMBER, CRIMSON, GOLD, JADE, Hud
from .scene import StreetScene
from .sim import Event, TrafficSim

MIN_FOV = 63.0
MAX_FOV = 72.0
LOOK_YAW = 169.0


class PatineteNoMueras:
    """Juego de un jugador con controles de movimiento y touch."""

    def __init__(self, manifest: GameManifest) -> None:
        self.manifest = manifest
        self.ctx: GameContext | None = None
        self.base: Any = None
        self.root: Any = None
        self.ui_root: Any = None
        self.scene: StreetScene | None = None
        self.hud: Hud | None = None
        self.sim = TrafficSim()
        self.reader = ControlReader()
        self.state = "title"
        self.controls = Controls()
        self.action_down = False
        self.look = 0.0
        self.look_lock = 0.0
        self.shake = 0.0
        self.elapsed = 0.0
        self.fov = MIN_FOV
        self._saved_cam: tuple[Any, Any, float, float] | None = None

    # -- ciclo de vida ------------------------------------------------------

    def start(self, ctx: GameContext) -> None:
        self.ctx = ctx
        self.base = ctx.base
        self.root = ctx.scene.attach_new_node("patinete-no-mueras")
        self.ui_root = ctx.ui.attach_new_node("patinete-no-mueras-ui")
        self._save_camera()
        self.sim.reset()
        self.reader.reset()
        self.state = "title"
        self.look = 0.0
        self.look_lock = 0.0
        self.shake = 0.0
        self.elapsed = 0.0
        self.fov = MIN_FOV
        self.scene = StreetScene(self.base, self.root)
        self.hud = Hud(self.ui_root)
        self.hud.show_title()
        self.scene.update(self.sim, 0.0, 0.0)
        self._update_camera(0.0, look_back=False)

    def stop(self) -> None:
        if self.hud is not None:
            self.hud.destroy()
            self.hud = None
        if self.scene is not None:
            self.scene.destroy()
            self.scene = None
        self._restore_camera()
        if self.ui_root is not None:
            self.ui_root.remove_node()
            self.ui_root = None
        if self.root is not None:
            self.root.remove_node()
            self.root = None
        self.ctx = None
        self.base = None

    # -- frame --------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.ctx is None or self.scene is None or self.hud is None:
            return
        dt = min(max(dt, 0.0), 0.1)
        self.elapsed += dt
        frame = self.ctx.input_state.primary_frame()
        controls = self.reader.read(frame)
        self.controls = controls

        pressed_action = frame is not None and frame.button("cross")
        action_edge = pressed_action and not self.action_down
        self.action_down = pressed_action

        if self.state == "title":
            if action_edge:
                self._begin_ride()
        elif self.state == "ride":
            events = self.sim.step(dt, controls.steer, controls.brake)
            self._handle_events(events)
            if self.sim.game_over:
                self.state = "gameover"
                self.hud.show_game_over(int(self.sim.distance), self.sim.points)
        elif self.state == "gameover" and action_edge:
            self._begin_ride()

        look_target = float(controls.look) if self.state == "ride" else 0.0
        if self.look_lock > 0.0:
            self.look_lock = max(0.0, self.look_lock - dt)
            look_target = 0.0
        response = 1.0 - math.exp(-max(dt, 0.0001) / 0.09)
        self.look += (look_target - self.look) * response
        if abs(self.look) < 0.005:
            self.look = 0.0
        self.shake = max(0.0, self.shake - dt * 2.4)

        self.scene.update(self.sim, controls.steer, abs(self.look))
        self._update_camera(dt, look_back=abs(self.look) > 0.4)
        self.hud.update(
            self.sim,
            looking_back=abs(self.look) > 0.35,
            motion=controls.motion,
            braking=controls.brake,
            dt=dt,
        )

    def _begin_ride(self) -> None:
        self.sim.reset()
        self.state = "ride"
        self.look = 0.0
        self.look_lock = 0.45
        self.shake = 0.0
        assert self.hud is not None
        self.hud.show_ride()
        self.hud.set_message("", GOLD, 0.0)
        self.hud.set_submessage("")
        self.hud.set_warning("", CRIMSON, 0.0)
        if self.ctx is not None:
            self.ctx.phone.vibrate([30, 40, 30])
            self.ctx.phone.tone(520, 90, volume=0.25)

    # -- eventos ------------------------------------------------------------

    def _handle_events(self, events: list[Event]) -> None:
        assert self.hud is not None and self.ctx is not None
        phone = self.ctx.phone
        for event in events:
            if event.kind == "crash":
                self.shake = 0.9
                self.hud.flash(0.55)
                self.hud.set_message("¡GOLPE!", CRIMSON, 1.6)
                self.hud.set_submessage("No mires solo adelante", 2.2)
                phone.vibrate([70, 40, 120])
                phone.tone(90, 220, volume=0.5)
            elif event.kind == "red":
                self.shake = 0.3
                self.hud.flash(0.32)
                self.hud.set_message("SEMAFORO EN ROJO", CRIMSON, 1.6)
                self.hud.set_submessage("Multa y trafico cruzando", 2.0)
                phone.vibrate([150, 60, 150])
                phone.tone(190, 200, volume=0.4)
            elif event.kind == "green":
                self.hud.set_message("VERDE", JADE, 0.9)
                phone.tone(660, 70, volume=0.18)
            elif event.kind == "near":
                self.hud.set_message("¡ROCE!", GOLD, 0.9)
                self.hud.set_submessage(f"+{event.value} por pasada cerca", 1.4)
                phone.tone(880, 50, volume=0.2)
            elif event.kind == "rear":
                side = "IZQUIERDA" if event.side < 0 else "DERECHA"
                self.hud.set_warning(f"¡VIENE ALGO POR TU {side}!", CRIMSON, 1.2)
                phone.tone(430, 70, volume=0.16)
            elif event.kind == "bus":
                self.hud.set_message("¡COLECTIVO!", AMBER, 1.2)
                self.hud.set_submessage("Se tira al carril derecho", 1.6)
                phone.tone(300, 120, volume=0.25)
            elif event.kind == "curb":
                self.shake = max(self.shake, 0.2)
                self.hud.set_submessage("¡Borde!", 0.8)

    # -- camara -------------------------------------------------------------

    def _update_camera(self, dt: float, *, look_back: bool) -> None:
        if self.base is None or self.scene is None:
            return
        sim = self.sim
        speed_ratio = min(1.0, sim.player_speed_kmh / 40.0)
        bob = math.sin(self.elapsed * 11.0) * 0.004 * speed_ratio
        if self.shake > 0.0:
            shake_x = math.sin(self.elapsed * 97.0) * self.shake * 0.055
            shake_z = math.cos(self.elapsed * 83.0) * self.shake * 0.045
            shake_r = math.sin(self.elapsed * 61.0) * self.shake * 2.5
        else:
            shake_x = shake_z = shake_r = 0.0
        cam_x = sim.player_x + sim.lean * 0.10 + self.look * 0.26 + shake_x
        self.base.cam.set_pos(cam_x, -0.28, 1.62 + bob + shake_z)
        yaw = -self.look * LOOK_YAW
        roll = -sim.lean * 3.5 + shake_r
        self.base.cam.set_hpr(yaw, -5.0, roll)
        target_fov = MIN_FOV + (MAX_FOV - MIN_FOV) * speed_ratio
        if look_back:
            target_fov += 4.0
        if dt > 0.0:
            self.fov += (target_fov - self.fov) * min(1.0, dt * 3.5)
        self.base.camLens.setFov(self.fov)

    def _save_camera(self) -> None:
        if self.base is None:
            return
        cam = self.base.cam
        self._saved_cam = (
            cam.get_pos(),
            cam.get_hpr(),
            self.base.camLens.getFov(),
            self.base.camLens.getNear(),
        )
        self.base.camLens.setNear(0.06)

    def _restore_camera(self) -> None:
        if self.base is None or self._saved_cam is None:
            return
        pos, hpr, fov, near = self._saved_cam
        self.base.cam.set_pos(pos)
        self.base.cam.set_hpr(hpr)
        self.base.camLens.setFov(fov)
        self.base.camLens.setNear(near)
        self._saved_cam = None
