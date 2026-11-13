"""Achievements: what unlocks them, who gets them, and that they are kept."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))

import achievements as A
import data as D
from engine import Game


def game(challenge=(), factions=None):
    return Game([("Ann", False), ("AI_1", True)], seed=4, challenge=challenge, factions=factions)


def finish(g, winner=0):
    """End the game now, with this player far ahead."""
    g.players[winner].gold = 400
    g.max_turns = g.turn
    g._end_turn()
    assert g.phase == "end"


def test_there_are_29_achievements_in_6_groups():
    assert len(A.ACHIEVEMENTS) == 29 and {a[1] for a in A.ACHIEVEMENTS} == set(A.GROUPS)
    assert len(A.BY_KEY) == 29


def test_buildings():
    g = game()
    p = g.players[0]
    assert A.reached(g, 0) == []
    p.buildings += ["temple"]
    assert "tier4" in A.reached(g, 0) and "two_tier4" not in A.reached(g, 0)
    p.buildings += ["bank", "castle"]
    assert {"two_tier4", "castle"} <= set(A.reached(g, 0))
    p.buildings += ["farm"] * 12
    assert "fifteen" in A.reached(g, 0)


def test_the_bank_counts_its_gold():
    g = game()
    p = g.players[0]
    p.buildings.append("bank")
    p.gold = 80
    g._produce(p)
    assert p.stats["bank_best_turn"] == 15 and "bank15" in A.reached(g, 0)
    for _ in range(3):
        g._produce(p)
    assert p.stats["bank_gold"] >= 50 and "bank50" in A.reached(g, 0)


def test_three_buildings_in_one_turn():
    g = game()
    p = g.players[0]
    for _ in range(3):
        p.note(f"built_turn_{g.turn}")
        p.note("most_built_in_a_turn", p.stats[f"built_turn_{g.turn}"], best=True)
    assert "three_in_turn" in A.reached(g, 0)


def test_pawns_and_mobs():
    g = game()
    p = g.players[0]
    p.note("recruited_champion")
    p.note("thief_steals", 5)
    p.note("win_vp_beast_tamer", 5)
    p.note("beat_Skeletons", 6, best=True)
    got = set(A.reached(g, 0))
    assert {"black_knight", "thief", "ram"} <= got and "skeletons7" not in got
    p.note("beat_Skeletons", 7, best=True)
    assert "skeletons7" in A.reached(g, 0)


def test_end_of_game_ones_wait_for_the_end():
    g = game()
    p = g.players[0]
    for x in p.pawns:
        x.kind = "warrior"
    while len(p.pawns) < g.pawn_limit(0):
        g.add_pawn(0, "warrior")
    assert "full" not in A.reached(g, 0) and "no_peasant" not in A.reached(g, 0)
    finish(g)
    got = set(A.reached(g, 0))
    assert {"full", "no_peasant", "gold100", "win"} <= got
    assert "win" not in A.reached(g, 1)  # the computer never gets them anyway, and it lost


def test_challenges_and_factions():
    g = game(challenge=("poor", "weak"), factions=["goblins", "dwarves"])
    finish(g)
    got = set(A.reached(g, 0))
    assert {"win", "win_poor", "win_weak", "win_both", "win_goblins"} <= got
    assert "win_dwarves" not in got and "no_peasant" not in got  # a faction game doesn't count for it


def test_losing_or_no_computer_gives_no_win():
    g = game()
    finish(g, winner=1)
    assert "win" not in A.reached(g, 0)
    g = Game([("Ann", False), ("Bob", False)], seed=4)
    finish(g)
    assert "win" not in A.reached(g, 0)


def test_the_tracker_saves_once_and_skips_the_computer():
    g = game()
    g.players[0].buildings.append("castle")
    g.players[1].buildings.append("bank")
    tracker = A.Tracker()
    assert tracker.update(g) == [("castle", "Ann")]
    assert tracker.update(g) == []
    assert "castle" in A.Tracker().unlocked and "tier4" not in A.Tracker().unlocked


def test_games_can_opt_out():
    g = game()
    g.players[0].buildings.append("castle")
    g.no_achievements = True
    assert A.Tracker().update(g) == []
