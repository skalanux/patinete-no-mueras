"""Lectura de controles: inclinacion, touch y mirada atras.

Sin sensores el juego sigue siendo jugable: arrastrar el dedo dobla y la franja
inferior del touchpad frena. Con sensores, inclinar el telefono dobla y tirarlo
hacia atras frena. × mira por encima del hombro izquierdo; × mas un toque en la
mitad derecha mira por el hombro derecho.
"""

from __future__ import annotations

from dataclasses import dataclass

from toxinator.api import ControllerFrame

STEER_DEADZONE = 2.5
STEER_RANGE = 30.0
BRAKE_BETA = 14.0
BRAKE_TOUCH_Y = 0.26
DRAG_SPAN = 0.20
LOOK_TOUCH_X = 0.52


@dataclass(frozen=True, slots=True)
class Controls:
    steer: float = 0.0
    brake: bool = False
    look: int = 0
    motion: bool = False


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ControlReader:
    """Convierte frames del celular en controles estables para el juego."""

    def __init__(self) -> None:
        self.motion = False
        self._touch_id: int | None = None
        self._origin_x = 0.5
        self._brake_touch = False

    def reset(self) -> None:
        self.motion = False
        self._touch_id = None
        self._origin_x = 0.5
        self._brake_touch = False

    def read(self, frame: ControllerFrame | None) -> Controls:
        if frame is None:
            self._touch_id = None
            self._brake_touch = False
            return Controls(motion=self.motion)

        _, beta, gamma = frame.orientation
        if abs(beta) + abs(gamma) > 3.5:
            self.motion = True

        steer = 0.0
        brake = False
        if self.motion:
            if abs(gamma) > STEER_DEADZONE:
                steer = _clamp(gamma / STEER_RANGE, -1.0, 1.0)
            brake = beta > BRAKE_BETA
        else:
            x = self._track_touch(frame)
            if x is not None:
                steer = _clamp((x - self._origin_x) / DRAG_SPAN, -1.0, 1.0)
                brake = self._brake_touch
            if self._brake_touch or (frame.touch and frame.touch[0].y < BRAKE_TOUCH_Y):
                brake = True

        look = 0
        if frame.button("cross"):
            side = -1
            for point in frame.touch:
                if point.x > LOOK_TOUCH_X:
                    side = 1
                    break
            look = side

        return Controls(steer=steer, brake=brake, look=look, motion=self.motion)

    def _track_touch(self, frame: ControllerFrame) -> float | None:
        if not frame.touch:
            self._touch_id = None
            self._brake_touch = False
            return None
        point = frame.touch[0]
        if self._touch_id != point.id:
            self._touch_id = point.id
            self._origin_x = point.x
            self._brake_touch = point.y < BRAKE_TOUCH_Y
        return point.x
