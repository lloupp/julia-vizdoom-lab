# Reaproveitando a camada de decisão em lloupp/minecraft-mbot

O pacote `decision/` não importa nada de `vizdoom_env/` nem de VizDoom. Para
reaproveitá-lo no `minecraft-mbot`:

1. **Copie `decision/` inteiro** para o projeto do bot (ou publique-o como
   pacote interno instalável).
2. **Produza um `GameState`** (`decision/state.py`) a partir do estado real
   do bot no Minecraft: vida, munição/durabilidade de item equivalente,
   inimigos visíveis, distância do inimigo mais próximo, item de cura
   visível, item de recurso (equivalente a munição) visível.
3. **Escreva um executor próprio** para o Minecraft, análogo a
   `vizdoom_env/executor.py`: uma função pura `Action -> comandos do bot`
   (mover, atacar, abrir inventário, etc.), sem aleatoriedade.
4. **Reaproveite sem alterar**:
   - `decision/actions.py` — as 6 ações (ou estenda com novas, mantendo o
     padrão de `ACTION_DESCRIPTIONS` para o Julia-1).
   - `decision/agents/rule_based.py`, `julia.py`, `fallback.py`,
     `anti_loop.py` — funcionam com qualquer `GameState`/executor.
   - `decision/logging.py` — mesmo formato de log JSONL.
5. Ajuste os textos em `ACTION_DESCRIPTIONS` (`decision/actions.py`) se o
   vocabulário de ações mudar para o contexto do Minecraft — é o único
   lugar que descreve as ações para o Julia-1.

O `AntiLoopGuard` e o `JuliaWithFallbackAgent` (com `confidence_threshold`
configurável) funcionam sem mudanças, pois dependem apenas da interface
`DecisionAgent`/`GameState`/`Decision`, não de VizDoom.
