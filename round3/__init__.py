"""Round 3: recommended typed-decision usage for VizDoom.

This package is intentionally additive. Rounds 1 and 2 remain untouched.
"""

from round3.agent import Round3ModelAgent
from round3.backends import JuliaBackend, LayaBackend

__all__ = ["Round3ModelAgent", "JuliaBackend", "LayaBackend"]
