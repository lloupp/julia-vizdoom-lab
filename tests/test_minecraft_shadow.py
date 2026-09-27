from minecraft_shadow import MINECRAFT_ACTIONS, MinecraftJuliaShadow


class FakeEngine:
    def __init__(self, choice="craft", confidence=0.8):
        self.choice = choice
        self.confidence = confidence

    def predict(self, state, questions):
        offered = list(questions["action"]["criteria"])
        probs = {a: (self.confidence if a == self.choice else 0.0) for a in offered}
        return {"answers": {"action": {
            "choice": self.choice,
            "probabilities": probs,
            "max_probability": self.confidence,
        }}}


def test_shadow_uses_shared_minecraft_vocabulary():
    assert set(MINECRAFT_ACTIONS) == {
        "gather", "craft", "smelt", "eat", "move", "deposit",
        "withdraw", "build", "fight", "wait", "stop",
    }


def test_shadow_returns_valid_choice_without_executing():
    result = MinecraftJuliaShadow(FakeEngine()).decide(
        {"health": 20, "food": 20, "objective": "craft_pickaxe", "inventory": {"cobblestone": 3}},
        ["gather", "craft", "wait"],
    )
    assert result.action == "craft"
    assert result.valid is True
    assert result.confidence == 0.8


def test_shadow_marks_model_choice_outside_allowlist_invalid():
    result = MinecraftJuliaShadow(FakeEngine("bash", 0.99)).decide({}, ["craft", "wait"])
    assert result.valid is False
    assert result.error == "invalid_action"
