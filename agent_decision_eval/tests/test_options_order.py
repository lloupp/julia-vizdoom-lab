from agent_decision_eval.actions import ALL_ACTIONS, options_for_task


def test_returns_a_permutation_of_all_actions():
    order = options_for_task("read_01")
    assert set(order) == set(ALL_ACTIONS)
    assert len(order) == len(ALL_ACTIONS)


def test_deterministic_for_the_same_task_id():
    assert options_for_task("read_01") == options_for_task("read_01")


def test_varies_across_different_task_ids():
    orders = {tuple(options_for_task(f"task_{i}")) for i in range(20)}
    # Not every task needs a unique order, but 20 tasks all landing on the
    # exact same permutation would mean the shuffle isn't doing anything.
    assert len(orders) > 1
