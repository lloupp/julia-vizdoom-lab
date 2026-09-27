# Minecraft shadow evaluation

Julia-1 must remain **shadow-only** until it passes the Minecraft-specific gates.
The existing VizDoom round 2 found strong option-order sensitivity, so a high
raw `max_probability` is not sufficient evidence for execution authority.

## Shared contract

Actions: `gather craft smelt eat move deposit withdraw build fight wait stop`.

Input is the minimal Minecraft state emitted by `minecraft-mbot`: health,
hunger, objective and inventory. The shadow evaluator returns action,
raw confidence, probabilities, latency, validity and error. It never executes
an action.

## Gate before active use

Compare the same held-out states across deterministic rules, Conversa-LLM and
Julia-1. Record accuracy against expected action, invalid-action rate, latency,
agreement, fallback rate and option-order invariance. Julia-1 remains shadow
when reordering the exact same offered actions changes the selected action
beyond the accepted experimental threshold.

Runtime success in VizDoom does not approve Minecraft. Final approval requires
a separate real-server Minecraft 1.20.1 run with the executor safety checks
enabled.
