# Patinete No Mueras

Juego POV para la consola **Toxinator**: vas en monopatín eléctrico por una
avenida de tres carriles, de noche, y tenés que sobrevivir al tráfico de la
ciudad. Respetá los semáforos, esquivá a los que hacen cualquier cosa y mirá
atrás antes de cambiar de carril.

```bash
cd /home/ska/Projects/toxinator
uv run toxinator play patinete-no-mueras
uv run toxinator play patinete-no-mueras --demo
```

La consola lo lista en la biblioteca si el symlink existe en
`~/Projects/toxinator-games` (lo crea `toxinator install`).

## Cómo se juega

| Acción | Movimiento (HTTPS) | Touch (fallback) |
|---|---|---|
| Doblar | incliná el teléfono a izquierda/derecha | arrastrá el dedo a los lados |
| Frenar | tirá el teléfono hacia atrás | tocá la franja inferior del touchpad |
| Mirar atrás | **mantené ×** (hombro izquierdo) | **×** + toque en la mitad derecha |
| Arrancar / reintentar | **×** | **×** |

El monopatín acelera solo hasta 40 km/h. Toda la dificultad está en elegir
cuándo frenar. Los sensores arrancan solos (en iOS, el primer toque concede el
permiso). Sin sensores el juego sigue siendo jugable: el arrastre dobla y la
franja inferior frena. **○** queda para volver al launcher. En teclado, × es
**Enter** o **J**; el mouse reemplaza al dedo.

El teléfono vibra y suena en choques, multas, bocinas y semáforos en verde. Si
el dispositivo no soporta vibración/audio, el juego sigue igual.

## Qué hay en la avenida

- **Semáforos**: verde, amarillo y rojo, con ciclo propio por esquina. Si cruzás
  el stop line en rojo te multan y el tráfico perpendicular empieza a cruzar.
  El HUD muestra el estado y la distancia al próximo semáforo.
- **Autos**: 80 km/h. Respetan el semáforo, frenan detrás del que tienen
  adelante y a veces cambian de carril si están trabados.
- **Taxis**: 100 km/h. Los más apurados: cambian de carril para pasar y llegan
  desde atrás.
- **Colectivos**: 60 km/h. Se abren al carril derecho antes de la parada y
  frenan en la esquina para subir pasajeros. Si vas por la derecha, te tiran
  encima.
- **Bicicletas**: 20 km/h. No respetan semáforos, se cruzan entre carriles y
  también aparecen cruzando en rojo.
- **Motos**: 85 km/h. Pasan por la izquierda o por la derecha, entre carriles,
  sin frenar por vos. Las más peligrosas.

Vos no ves lo que viene atrás: el aviso del HUD y el tono te dicen que algo se
acerca, pero el lado y la distancia los tenés que confirmar girando la cabeza
con **×**. Mientras mirás atrás no ves adelante, así que es un riesgo real.

## Puntaje

- Distancia recorrida (1 punto por metro).
- +60 por cruzar en verde.
- +25 por roce a otro vehículo.
- -120 por cruzar en rojo.

Tenés 3 vidas. Cada choque te deja sin velocidad, con sacudida de cámara y un
segundo de invulnerabilidad. Al tercero se termina la partida.

## Estructura

```text
src/patinete_no_mueras/
├── __init__.py      # create_game(manifest)
├── manifest.toml    # perfil del celular y metadata
├── game.py          # lifecycle, input, cámara, eventos
├── controls.py      # inclinación/touch/mirada atrás (puro)
├── hud.py           # textos, overlays y avisos
├── scene.py         # avenida, edificios, semáforos y vehículos 3D
├── sim.py           # reglas puras: semáforos, tráfico, choques
└── ...
tests/
├── test_controls.py
└── test_sim.py
```

`sim.py` y `controls.py` no importan Panda3D, así que se testean sin abrir
ventana.

## Tests y calidad

```bash
cd /home/ska/Projects/toxinator-games/patinete-no-mueras
/home/ska/Projects/toxinator/.venv/bin/pytest -q
/home/ska/Projects/toxinator/.venv/bin/ruff check src tests
/home/ska/Projects/toxinator/.venv/bin/mypy
```

Para ver un frame sin ventana:

```bash
cd /home/ska/Projects/toxinator
uv run toxinator play patinete-no-mueras --offscreen \
  --screenshot /tmp/patinete.png --screenshot-after 4 --seconds 6
```

## Reglas de la plataforma

- Solo se importa `toxinator.api` del runtime.
- No crea `ShowBase` ni ventanas: usa `ctx.scene` y `ctx.ui`.
- Lee el input desde `ctx.input_state.primary_frame()`; **○** es de la plataforma.
- Restaura la cámara y el lente en `stop`.
- `requires_api = "0.2"`.
