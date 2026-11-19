"""Tests de lectura de controles (sin Panda3D)."""

from __future__ import annotations

import pytest
from toxinator.api import ControllerFrame, TouchPoint

from patinete_no_mueras.controls import ControlReader


def frame(
    *,
    buttons: frozenset[str] = frozenset(),
    orientation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    touch: tuple[TouchPoint, ...] = (),
) -> ControllerFrame:
    return ControllerFrame(
        controller_id="p1",
        timestamp=0.0,
        buttons=buttons,
        orientation=orientation,
        touch=touch,
    )


def test_without_sensors_the_game_uses_touch() -> None:
    reader = ControlReader()
    controls = reader.read(frame(touch=(TouchPoint(0, 0.5, 0.5),)))
    assert not controls.motion
    assert controls.steer == 0.0
    assert not controls.brake


def test_motion_mode_steers_with_roll() -> None:
    reader = ControlReader()
    controls = reader.read(frame(orientation=(0.0, 0.0, 15.0)))
    assert controls.motion
    assert 0.45 < controls.steer < 0.55
    assert not controls.brake


def test_motion_mode_brakes_while_tilting_back() -> None:
    reader = ControlReader()
    controls = reader.read(frame(orientation=(0.0, 20.0, 0.0)))
    assert controls.brake


def test_touch_drag_steers_from_its_origin() -> None:
    reader = ControlReader()
    reader.read(frame(touch=(TouchPoint(1, 0.4, 0.6),)))
    controls = reader.read(frame(touch=(TouchPoint(1, 0.6, 0.6),)))
    assert controls.motion is False
    assert controls.steer == pytest.approx(1.0)


def test_bottom_strip_brakes() -> None:
    reader = ControlReader()
    controls = reader.read(frame(touch=(TouchPoint(1, 0.5, 0.1),)))
    assert controls.brake


def test_a_looks_back_left_by_default() -> None:
    reader = ControlReader()
    controls = reader.read(frame(buttons=frozenset({"A"})))
    assert controls.look == -1


def test_a_plus_right_touch_looks_back_right() -> None:
    reader = ControlReader()
    controls = reader.read(
        frame(
            buttons=frozenset({"A"}),
            touch=(TouchPoint(1, 0.8, 0.6),),
        )
    )
    assert controls.look == 1


def test_touch_release_resets_the_drag_origin() -> None:
    reader = ControlReader()
    reader.read(frame(touch=(TouchPoint(1, 0.2, 0.6),)))
    reader.read(frame())
    controls = reader.read(frame(touch=(TouchPoint(2, 0.5, 0.6),)))
    assert controls.steer == 0.0
