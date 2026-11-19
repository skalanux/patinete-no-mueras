from __future__ import annotations

from toxinator.api import Game, GameManifest

from .game import PatineteNoMueras


def create_game(manifest: GameManifest) -> Game:
    return PatineteNoMueras(manifest)
