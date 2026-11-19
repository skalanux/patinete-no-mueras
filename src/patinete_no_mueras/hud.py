"""HUD del juego: velocidad, semaforo, avisos y pantallas de estado."""

from __future__ import annotations

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import CardMaker, NodePath, TextNode, Vec4

from .sim import GREEN, RED, YELLOW, TrafficSim

CREAM = Vec4(0.94, 0.95, 1.0, 1.0)
MUTED = Vec4(0.58, 0.64, 0.76, 1.0)
GOLD = Vec4(0.98, 0.78, 0.32, 1.0)
CRIMSON = Vec4(1.0, 0.28, 0.26, 1.0)
JADE = Vec4(0.30, 0.95, 0.58, 1.0)
AMBER = Vec4(1.0, 0.72, 0.18, 1.0)
SHADOW = Vec4(0.0, 0.0, 0.0, 0.8)
LIGHT_COLORS = {GREEN: JADE, YELLOW: AMBER, RED: CRIMSON}
LIGHT_NAMES = {GREEN: "VERDE", YELLOW: "AMARILLO", RED: "ROJO"}


class Hud:
    """Textos 2D y overlays del juego."""

    def __init__(self, root: NodePath) -> None:
        self.root = root
        self.texts: dict[str, OnscreenText] = {}
        self.flash_card = self._card(0.0, 6)
        self.overlay_card = self._card(0.0, 4)
        self.message = ""
        self.message_color = GOLD
        self.message_timer = 0.0
        self.submessage_timer = 0.0
        self.warning_timer = 0.0
        self.flash_alpha = 0.0
        self._build()

    def _card(self, alpha: float, sort: int) -> NodePath:
        maker = CardMaker("hud-card")
        maker.set_frame(-2.0, 2.0, -1.2, 1.2)
        card = self.root.attach_new_node(maker.generate())
        card.set_color(Vec4(0.01, 0.02, 0.04, alpha))
        card.set_transparency(1)
        card.set_bin("fixed", sort)
        card.set_depth_test(False)
        card.set_depth_write(False)
        return card

    def _text(
        self,
        key: str,
        *,
        pos: tuple[float, float],
        scale: float,
        color: Vec4,
        align: int = TextNode.ACenter,
        sort: int = 50,
    ) -> OnscreenText:
        text = OnscreenText(
            text="",
            parent=self.root,
            pos=pos,
            scale=scale,
            fg=color,
            align=align,
            shadow=SHADOW,
            mayChange=True,
        )
        text.set_bin("fixed", sort)
        text.set_depth_test(False)
        self.texts[key] = text
        return text

    def _build(self) -> None:
        self._text(
            "distance",
            pos=(-1.52, 0.84),
            scale=0.058,
            color=CREAM,
            align=TextNode.ALeft,
        )
        self._text(
            "points",
            pos=(-1.52, 0.77),
            scale=0.034,
            color=GOLD,
            align=TextNode.ALeft,
        )
        self._text(
            "lives",
            pos=(1.52, 0.86),
            scale=0.042,
            color=CREAM,
            align=TextNode.ARight,
        )
        self._text(
            "mode",
            pos=(1.52, 0.79),
            scale=0.026,
            color=MUTED,
            align=TextNode.ARight,
        )

        self._text("light", pos=(0.0, 0.925), scale=0.072, color=CREAM)
        self._text("light_dist", pos=(0.0, 0.845), scale=0.034, color=MUTED)

        self._text(
            "speed",
            pos=(1.52, -0.86),
            scale=0.062,
            color=CREAM,
            align=TextNode.ARight,
        )
        self._text(
            "speed_bar",
            pos=(1.52, -0.925),
            scale=0.033,
            color=JADE,
            align=TextNode.ARight,
        )

        self._text(
            "hint",
            pos=(-1.52, -0.88),
            scale=0.038,
            color=MUTED,
            align=TextNode.ALeft,
        )
        self._text(
            "look",
            pos=(-1.52, -0.945),
            scale=0.038,
            color=GOLD,
            align=TextNode.ALeft,
        )

        self._text(
            "warning",
            pos=(0.0, -0.78),
            scale=0.060,
            color=CRIMSON,
        )
        self._text("brake", pos=(0.0, 0.21), scale=0.075, color=CRIMSON)
        self._text("message", pos=(0.0, 0.03), scale=0.12, color=GOLD)
        self._text("submessage", pos=(0.0, -0.09), scale=0.042, color=CREAM)

        self._text("screen_title", pos=(0.0, 0.52), scale=0.105, color=GOLD)
        self._text("screen_sub", pos=(0.0, 0.40), scale=0.040, color=CREAM)
        self._text("screen_body", pos=(0.0, -0.05), scale=0.038, color=MUTED)
        self._text("screen_footer", pos=(0.0, -0.46), scale=0.052, color=JADE)

        self.texts["hint"].setText("A: mirar atrás")
        self.texts["screen_title"].setText("PATINETE NO MUERAS")
        self.texts["screen_sub"].setText("Una avenida, tres carriles, cero segundos")
        self.texts["screen_body"].setText(
            "Incliná el teléfono para doblar\n"
            "Tiralo hacia atrás para frenar\n"
            "Mantené A para mirar atrás\n"
            "El semáforo manda: si cruzás en rojo, cruzan autos\n"
            "Colectivos, bicis, motos y taxis se mueven distinto\n"
            "Sin sensores: arrastrá y usá la franja inferior para frenar"
        )
        self.texts["screen_footer"].setText("A PARA ARRANCAR")
        self.set_screen("title")

    def set_screen(self, screen: str) -> None:
        title = screen == "title"
        game_over = screen == "gameover"
        hidden = screen == "ride"
        self.texts["screen_title"].setText(
            "PATINETE NO MUERAS" if title else "TE BAJASTE"
        )
        self.texts["screen_title"].setFg(GOLD if title else CRIMSON)
        self.texts["screen_sub"].setText(
            "Una avenida, tres carriles, cero segundos"
            if title
            else "La avenida no perdona"
        )
        self.texts["screen_body"].setText(
            (
                "Incliná el teléfono para doblar\n"
                "Tiralo hacia atrás para frenar\n"
                "Mantené A para mirar atrás\n"
                "El semáforo manda: si cruzás en rojo, cruzan autos\n"
                "Colectivos, bicis, motos y taxis se mueven distinto\n"
                "Sin sensores: arrastrá y usá la franja inferior para frenar"
            )
            if title
            else ""
        )
        self.texts["screen_footer"].setText(
            "A PARA ARRANCAR" if title else "A PARA OTRA VUELTA"
        )
        self.texts["screen_body"].setFg(MUTED if title else CREAM)
        for key in ("screen_title", "screen_sub", "screen_body", "screen_footer"):
            if hidden:
                self.texts[key].hide()
            else:
                self.texts[key].show()
        if hidden:
            self.overlay_card.hide()
        else:
            self.overlay_card.show()
            self.overlay_card.set_color(Vec4(0.01, 0.02, 0.04, 0.72 if title else 0.6))
        if game_over:
            self.texts["screen_body"].setText("")

    def update(
        self,
        sim: TrafficSim,
        *,
        looking_back: bool,
        motion: bool,
        braking: bool,
        dt: float,
    ) -> None:
        self.message_timer = max(0.0, self.message_timer - dt)
        if self.message_timer == 0.0:
            self.message = ""
        self.submessage_timer = max(0.0, self.submessage_timer - dt)
        if self.submessage_timer == 0.0:
            self.texts["submessage"].setText("")
        self.warning_timer = max(0.0, self.warning_timer - dt)
        if self.warning_timer == 0.0:
            self.texts["warning"].setText("")
        self.flash_alpha = max(0.0, self.flash_alpha - dt * 2.6)
        self.flash_card.set_color(Vec4(1.0, 0.12, 0.10, self.flash_alpha))
        if self.flash_alpha > 0.0:
            self.flash_card.show()
        else:
            self.flash_card.hide()

        self.texts["distance"].setText(f"{int(sim.distance):04d} m")
        self.texts["points"].setText(f"PUNTOS {sim.points:05d}")
        lives = sim.lives
        self.texts["lives"].setText(f"VIDAS {lives}/{3}")
        self.texts["lives"].setFg(CRIMSON if lives <= 1 else CREAM)
        self.texts["mode"].setText("MOTION" if motion else "TOUCH")

        speed = round(sim.player_speed_kmh)
        self.texts["speed"].setText(f"{speed:02d} km/h")
        filled = round(sim.player_speed_kmh / 40.0 * 12.0)
        bar = "#" * filled + "-" * (12 - filled)
        self.texts["speed_bar"].setText(bar)

        light = sim.light_ahead()
        if light is None:
            self.texts["light"].setText("")
            self.texts["light_dist"].setText("")
        else:
            self.texts["light"].setText(
                f"{LIGHT_NAMES[light.state]}"
            )
            self.texts["light"].setFg(LIGHT_COLORS[light.state])
            distance = max(0, int(light.rel_y))
            self.texts["light_dist"].setText(f"A {distance} m")

        self.texts["look"].setText(
            "MIRANDO ATRÁS" if looking_back else "A: mirar atrás"
        )
        self.texts["look"].setFg(GOLD if looking_back else MUTED)
        if braking:
            self.texts["hint"].setText("FRENANDO")
        elif motion:
            self.texts["hint"].setText("Incliná para doblar")
        else:
            self.texts["hint"].setText("Arrastrá para doblar")
        self.texts["hint"].setFg(AMBER if braking else MUTED)

        self.texts["message"].setText(self.message)
        self.texts["message"].setFg(self.message_color)

        brake_warning = (
            light is not None
            and light.state == RED
            and 0.0 < light.rel_y < 65.0
            and sim.player_speed_kmh > 8.0
            and not sim.game_over
        )
        if brake_warning:
            self.texts["brake"].setText("¡FRENA!")
            self.texts["brake"].show()
            self.texts["brake"].setColorScale(1.0)
        else:
            self.texts["brake"].hide()

    def set_message(
        self, text: str, color: Vec4 = GOLD, duration: float = 1.4
    ) -> None:
        self.message = text
        self.message_color = color
        self.message_timer = duration

    def set_submessage(self, text: str, duration: float = 2.0) -> None:
        self.texts["submessage"].setText(text)
        self.submessage_timer = duration

    def set_warning(self, text: str, color: Vec4, duration: float = 1.2) -> None:
        self.texts["warning"].setText(text)
        self.texts["warning"].setFg(color)
        self.warning_timer = duration

    def flash(self, alpha: float = 0.42) -> None:
        self.flash_alpha = max(self.flash_alpha, alpha)
        self.flash_card.show()

    def show_title(self) -> None:
        self.set_screen("title")

    def show_ride(self) -> None:
        self.set_screen("ride")

    def show_game_over(self, distance: int, points: int) -> None:
        self.message = ""
        self.message_timer = 0.0
        self.submessage_timer = 0.0
        self.warning_timer = 0.0
        self.texts["submessage"].setText("")
        self.texts["warning"].setText("")
        self.set_screen("gameover")
        self.texts["screen_sub"].setText(f"DISTANCIA {distance:04d} m")
        self.texts["screen_body"].setText(f"PUNTOS {points:05d}")
        self.texts["screen_body"].setFg(CREAM)
        self.texts["screen_body"].show()

    def destroy(self) -> None:
        for text in self.texts.values():
            text.remove_node()
        self.texts.clear()
        self.flash_card.remove_node()
        self.overlay_card.remove_node()
