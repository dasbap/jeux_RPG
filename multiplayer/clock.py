import math
import time


class GameClock:
    ratio = 20.0

    def __init__(self, epoch_wall, epoch_game=0.0, monotonic=time.monotonic, wall=time.time, minimum_game=0.0):
        self._monotonic = monotonic
        self._origin = monotonic()
        self._game = max(minimum_game, epoch_game + max(0.0, wall() - epoch_wall) * self.ratio)

    def now(self):
        return self._game + max(0.0, self._monotonic() - self._origin) * self.ratio

    @classmethod
    def real_seconds(cls, game_seconds):
        if not math.isfinite(game_seconds) or game_seconds < 0:
            raise ValueError("Durée invalide")
        return game_seconds / cls.ratio
