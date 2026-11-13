"""The computer players' fixed rules: forced recruits, fearless fights and the last turn."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))

import ai
from engine import FIGHT, HOME, TOWN, Game


def ai_game(seed=5):
    return Game([("A", True), ("B", True)], seed=seed)


def to_actions(g):
    while g.phase == "deploy":
        g.done_placing(g.active)


def test_forced_recruit_never_buys_a_peasant_and_needs_the_gold():
    g = ai_game()
    to_actions(g)
    pid = g.active
    p = g.players[pid]
    p.pawns[0].location = TOWN
    g.recruits[pid] = ["peasant", "warrior", "knight", "thief"]
    p.gold = 100
    index, lots = ai.forced_recruit(g, pid)
    assert index is not None and g.recruits[pid][index] != "peasant" and not lots
    p.gold = 0
    p.res = {r: 0 for r in p.res}
    assert ai.forced_recruit(g, pid) == (None, None)  # nothing to pay with


def test_forced_recruit_sells_only_what_the_next_building_does_not_need():
    g = ai_game()
    to_actions(g)
    pid = g.active
    p = g.players[pid]
    p.pawns[0].location = TOWN
    g.recruits[pid] = ["peasant", "warrior"]
    p.gold = 0
    p.res = {r: 0 for r in p.res}
    p.res.update({"wood": 30, "stone": 30, "food": 30, "iron": 30})
    target = ai.next_building(g, pid)
    keep = g.build_cost(pid, target)
    index, lots = ai.forced_recruit(g, pid)
    assert index is not None and lots
    for r, n in lots.items():
        assert p.res[r] - n >= keep.get(r, 0)  # the next building stays affordable


def test_no_forced_recruit_at_the_pawn_limit():
    g = ai_game()
    to_actions(g)
    pid = g.active
    p = g.players[pid]
    while len(p.pawns) < g.pawn_limit(pid):
        g.add_pawn(pid, "peasant")
    p.pawns[0].location = TOWN
    p.gold = 100
    assert ai.forced_recruit(g, pid) == (None, None)


def contest_game(kinds, turn=None):
    """Player 0 alone against a mob it can't beat, with pawns of these kinds."""
    g = ai_game()
    env = g.envs[0]
    env.mob = ("Skeletons", 9)
    p = g.players[0]
    p.pawns = []
    for kind in kinds:
        g.add_pawn(0, kind).location = env.eid
    if turn:
        g.turn = turn
    g.contest = {"env": env.eid, "players": [0], "stances": {}, "pending": [0]}
    g.active = 0
    return g


def test_a_hopeless_fight_is_left_by_pawns_that_can_be_wounded():
    assert ai._wanted_stance(contest_game(["peasant"]))[0] != FIGHT


def test_pawns_that_cant_be_wounded_always_fight():
    assert ai._wanted_stance(contest_game(["thief"]))[0] == FIGHT


def test_everyone_fights_on_the_last_turn():
    g = contest_game(["peasant"], turn=12)
    assert g.turn == g.max_turns and ai._wanted_stance(g)[0] == FIGHT


def test_on_the_last_turn_a_pawn_goes_to_town_first():
    g = ai_game()
    g.turn = g.max_turns
    g.phase = "deploy"
    pid = g.active
    for x in g.players[pid].pawns:
        x.placed, x.location = False, HOME
    ai.take_deploy(g)
    assert g.pawns_at(pid, TOWN)


def test_a_full_roster_replaces_its_weakest_pawn_when_the_gold_allows():
    g = ai_game()
    to_actions(g)
    pid = g.active
    p = g.players[pid]
    while len(p.pawns) < g.pawn_limit(pid):
        g.add_pawn(pid, "warrior")
    p.pawns[1].location = TOWN
    g.recruits[pid] = ["peasant", "knight"]
    p.gold = 0
    assert ai.upgrade_recruit(g, pid) == (None, None)  # no gold, no upgrade
    p.gold = 100
    index, uid = ai.upgrade_recruit(g, pid)
    assert g.recruits[pid][index] == "knight"
    assert next(x for x in p.pawns if x.uid == uid).kind == "peasant"  # the weakest one leaves
    for _ in range(20):  # builds and sales may come first
        if g.phase != "actions" or g.active != pid or any(x.kind == "knight" for x in p.pawns):
            break
        ai.take_action(g)
    assert any(x.kind == "knight" for x in p.pawns) and any(x.leaving for x in p.pawns)


def test_everything_is_sold_only_on_the_last_turn():
    g = ai_game()
    pid = g.active
    p = g.players[pid]
    p.res = {r: 0 for r in p.res}
    p.res.update({"wood": 9, "stone": 9})
    before_last = ai._lots_to_sell(g, pid, 1)
    assert before_last.get("wood", 0) < 9 or before_last.get("stone", 0) < 9  # turn 11 keeps what it needs
    assert ai._lots_to_sell(g, pid, 0) == {"wood": 9, "stone": 9}  # turn 12 sells it all


def test_looking_ahead_makes_a_legal_move_and_leaves_the_game_untouched():
    import copy
    from engine import Game
    game = Game([("Me", False), ("AI", True)], turns=12, seed=5)
    game.brains = {1: ai.load_for(12, 2, False)}
    ai.LOOKAHEAD = {"futures": 2, "margin": 6, "zones": 3}
    try:
        while not (game.phase == "deploy" and game.players[game.active].is_ai):
            ai.play_step(game)  # the human seat plays with the plain rules here
        before = copy.deepcopy(game.players[1].pawns)
        move = ai.lookahead_move(game)
        assert [x.__dict__ for x in game.players[1].pawns] == [x.__dict__ for x in before]
        if move:
            uid, destination = move
            assert uid in {x.uid for x in game.deployable(1)}
        placed = sum(x.placed for x in game.players[1].pawns)
        ai.take_deploy(game)
        assert sum(x.placed for x in game.players[1].pawns) == placed + 1
    finally:
        ai.LOOKAHEAD = None


def test_only_the_hard_computer_looks_ahead():
    from engine import Game
    easy = ai.load_for(12, 2, False)
    game = Game([("Easy", True), ("Hard", True)], turns=12, seed=8)
    game.brains = {0: easy, 1: ai.hard_brain(easy)}
    assert "lookahead" not in game.brains[0] and game.brains[1]["lookahead"]["futures"] == 4
    calls = []
    real = ai.lookahead_move
    ai.lookahead_move = lambda g, settings=None: calls.append(g.active) or real(g, settings)
    try:
        while game.turn < 2:
            ai.play_step(game) if not (game.phase == "harvest" and game.harvest_stage in ("next", "report")) else (
                game.harvest_next() if game.harvest_stage == "next" else game.ack_report())
    finally:
        ai.lookahead_move = real
    assert calls and set(calls) == {1}
