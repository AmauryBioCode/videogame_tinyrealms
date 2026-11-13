"""Run with:  python -m pytest tests   (from the jeu folder)"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game"))

import ai
import data as D
from engine import FIGHT, HOME, SPLIT, TOWN, YIELD, Game, GameError


def new_game(n=2, turns=12, seed=1, is_ai=False):
    return Game([(f"P{i}", is_ai) for i in range(n)], turns=turns, seed=seed)


def run_ai_game(game):
    guard = 0
    while game.phase != "end":
        guard += 1
        assert guard < 20000, "game does not finish"
        if game.phase == "harvest" and game.harvest_stage == "next":
            game.harvest_next()
        elif game.phase == "harvest" and game.harvest_stage == "report":
            game.ack_report()
        else:
            assert ai.play_step(game)


def to_actions(g):
    while g.phase == "deploy":
        g.done_placing(g.active)


def test_start_state():
    g = new_game(3)
    assert g.phase == "deploy" and len(g.envs) == 7
    for p in g.players:
        assert [x.kind for x in p.pawns] == ["peasant", "peasant"]
        assert p.buildings == []
    assert all(not g.recruits[pid] for pid in range(3))  # hidden while placing
    for e in g.envs:
        assert len(e.harvest) == 1 and e.prize


def test_placement_alternates_one_pawn_at_a_time():
    g = new_game()
    first = g.active
    g.send(first, g.players[first].pawns[0].uid, TOWN)
    assert g.active != first
    with pytest.raises(GameError):
        g.send(first, g.players[first].pawns[1].uid, TOWN)


def test_players_place_in_order_and_first_player_changes_each_turn():
    g = new_game(3, turns=2)
    seen = []
    while g.phase == "deploy" and len(seen) < 6:
        seen.append(g.active)
        g.send(g.active, g.deployable(g.active)[0].uid, g.envs[0].eid)
    assert seen == [0, 1, 2, 0, 1, 2]
    while g.phase == "actions":
        g.end_actions(g.active)
    while g.phase == "harvest":
        if g.harvest_stage == "next":
            g.harvest_next()
        elif g.harvest_stage == "stance":
            g.set_stance(g.active, YIELD)
        else:
            g.ack_report()
    assert g.turn == 2 and g.active == 1 and g.first == 1


def test_computer_always_sends_a_pawn_when_it_can():
    for seed in range(30):
        g = new_game(2, seed=seed, is_ai=True)
        while g.phase == "deploy":
            ai.play_step(g)
        for p in g.players:
            assert any(x.location != HOME for x in p.pawns)


def test_cannot_send_same_pawn_twice():
    g = new_game()
    a = g.active
    uid = g.players[a].pawns[0].uid
    g.send(a, uid, TOWN)
    g.done_placing(g.active)
    with pytest.raises(GameError):
        g.send(a, uid, g.envs[0].eid)


def test_build_needs_home_pawn_and_resources():
    g = new_game()
    a = g.active
    p = g.players[a]
    for pawn, place in zip(list(p.pawns), [TOWN, g.envs[0].eid]):
        g.send(a, pawn.uid, place)
        if g.phase == "deploy" and g.active != a:
            g.done_placing(g.active)
    assert g.phase == "actions"
    assert not g.can_build(a, "farm")[0]
    assert g.free_town(a)


def test_build_spends_and_uses_pawn():
    g = new_game()
    to_actions(g)
    a = g.active
    p = g.players[a]
    g.build(a, "farm")
    assert p.buildings == ["farm"] and p.res["wood"] == 0
    assert len(g.free_home(a)) == 1
    with pytest.raises(GameError):
        g.build(a, "farm")


def test_collected_resources_arrive_only_after_actions():
    g = new_game()
    env = g.envs[0]
    a = g.active
    p = g.players[a]
    before = sum(p.res.values())
    g.send(a, p.pawns[0].uid, env.eid)
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.phase == "actions":
        assert sum(p.res.values()) == before
        g.end_actions(g.active)
    assert g.phase == "harvest"
    g.harvest_next()
    assert sum(p.res.values()) > before


def test_recruit_and_sell_in_town():
    g = new_game()
    a = g.active
    p = g.players[a]
    g.send(a, p.pawns[0].uid, TOWN)
    g.done_placing(g.active)
    g.send(a, p.pawns[1].uid, g.envs[0].eid)
    while g.phase == "deploy":
        g.done_placing(g.active)
    gold = p.gold
    g.recruit(a, 0)
    assert p.gold == gold - 3 and len(p.pawns) == 3 and g.recruits[a][0] is None
    assert g.recruits[1 - a][0] == "peasant"
    expected = g.prices["wood"] * 2
    gold = p.gold
    g.sell(a, {"wood": 2})
    assert p.gold == gold + expected and p.res["wood"] == 0


def in_town(pawns=1):
    g = new_game()
    a = g.active
    p = g.players[a]
    for pawn in p.pawns[:pawns]:
        g.send(a, pawn.uid, TOWN)
        g.done_placing(g.active) if g.active != a and g.phase == "deploy" else None
    while g.phase == "deploy":
        g.done_placing(g.active)
    return g, a, p


def test_one_town_pawn_sells_then_recruits_with_the_gold():
    g, a, p = in_town()
    p.gold = 0
    p.res["iron"] = 3
    g.sell(a, {"iron": 3})
    assert p.gold >= 3
    assert g.can_recruit(a, 0)[0]
    g.recruit(a, 0)
    assert len(p.pawns) == 3


def test_one_town_pawn_recruits_then_sells():
    g, a, p = in_town()
    g.recruit(a, 0)
    g.sell(a, {"wood": 1})
    assert p.res["wood"] == 1 and len(p.pawns) == 3


def test_town_pawn_sells_as_often_as_it_likes_but_recruits_once():
    g, a, p = in_town()
    p.res["wood"] = 3
    p.gold = 20
    for _ in range(3):
        g.sell(a, {"wood": 1})
    assert p.res["wood"] == 0
    g.recruit(a, 0)
    assert not g.can_recruit(a, 1)[0]


def test_caravan_post_gives_one_extra_recruit():
    g, a, p = in_town()
    p.buildings.append("caravan_post")
    p.gold = 20
    g.recruit(a, 0)
    assert g.can_recruit(a, 1)[0]
    g.recruit(a, 1)
    assert not g.can_recruit(a, 2)[0]


def to_action_step(g):
    while g.phase == "deploy":
        g.done_placing(g.active)


def test_recruits_are_hidden_while_placing_and_the_same_for_everyone():
    g = new_game(3)
    assert not any(g.recruits.values())
    to_action_step(g)
    assert g.recruits[0] == g.recruits[1] == g.recruits[2]
    assert g.recruits[0][0] == "peasant" and len(g.recruits[0]) == 4


def test_a_bought_recruit_is_still_there_for_the_others():
    g = new_game(2)
    a = g.active
    b = 1 - a
    g.send(a, g.players[a].pawns[0].uid, TOWN)
    g.send(b, g.players[b].pawns[0].uid, TOWN)
    to_action_step(g)
    g.players[a].gold = g.players[b].gold = 30
    first = g.active
    other = 1 - first
    g.recruit(first, 1)
    g.end_actions(first)
    assert g.recruits[first][1] is None and g.recruits[other][1] is not None
    g.recruit(other, 1)
    assert g.players[other].pawns[-1].kind == g.players[first].pawns[-1].kind


def test_mob_limit_grows_by_one_each_turn():
    seen = set()
    for seed in range(60):
        g = new_game(2, seed=seed)
        assert all(e.mob is None for e in g.envs)
        for turn in range(2, 8):
            g.turn = turn
            g.reveal_all()
            count = sum(1 for e in g.envs if e.mob)
            assert count <= turn - 1
            seen.add((turn, count))
    assert (2, 1) in seen and (3, 2) in seen and (2, 2) not in seen


@pytest.mark.parametrize("players", [2, 3, 4])
def test_mob_limit_is_the_same_for_all_players(players):
    seen = set()
    for seed in range(100):
        g = new_game(players, seed=seed)
        for turn in range(2, 12):
            g.turn = turn
            g.reveal_all()
            seen.add(sum(1 for e in g.envs if e.mob))
    assert max(seen) == 2


@pytest.mark.parametrize("players,removed", [(2, 0), (3, 1), (4, 2)])
def test_strongest_mobs_stay_away_with_more_players(players, removed):
    seen = {}
    for seed in range(300):
        g = new_game(players, seed=seed)
        for turn in range(2, 12):
            g.turn = turn
            g.reveal_all()
            for e in g.envs:
                if e.mob:
                    seen.setdefault(e.eid, set()).add(e.mob)
    for zone, info in D.ENVIRONMENTS.items():
        by_strength = sorted(info["mobs"], key=lambda mob: mob[1])
        allowed = set(by_strength[:len(by_strength) - removed])
        assert seen.get(zone, set()) == allowed


def test_all_pawns_collect_the_one_shown_resource_and_it_changes():
    g = new_game()
    e = g.envs[0]
    e.harvest = ["stone"]
    e.mob = None
    a = g.active
    p = g.players[a]
    before = p.res["stone"]
    g.send(a, p.pawns[0].uid, e.eid)
    g.done_placing(g.active)
    g.send(a, p.pawns[1].uid, e.eid)
    while g.phase == "actions":
        g.end_actions(g.active)
    g.harvest_next()
    assert p.res["stone"] == before + 2
    values = set()
    for _ in range(40):
        g._reveal(e)
        values.add(e.harvest[0])
    assert len(values) > 1


def play_to_actions(g):
    while g.phase == "deploy":
        g.done_placing(g.active)


def test_prices_follow_the_new_ranges():
    seen = {r: [] for r in D.RESOURCE_IDS}
    for seed in range(400):
        g = new_game(seed=seed)
        for r, price in g.prices.items():
            seen[r].append(price)
    for r in ("wood", "stone", "food"):
        assert set(seen[r]) == {1}
    for r in ("iron", "herbs"):
        assert set(seen[r]) == {2}
    for r, low in (("amber", 3), ("pearl", 3), ("crystal", 5), ("mithril", 5)):
        assert set(seen[r]) == {low, low + 1, low + 2}
        assert seen[r].count(low + 1) > seen[r].count(low)
        assert seen[r].count(low + 1) > seen[r].count(low + 2)
    assert set(seen["relic"]) == {7, 8, 9, 10}
    assert seen["relic"].count(8) > seen["relic"].count(9)


def test_scout_is_gone():
    assert "scout" not in D.PAWNS and "scout" not in D.RECRUIT_POOL


def duel(prize=(("wood"), 2), mob=None, seed=1):
    """Two players, one pawn each, in the same environment."""
    g = new_game(2, seed=seed)
    e = g.envs[0]
    e.mob = mob
    e.prize = prize
    a = g.active
    b = next(p.pid for p in g.players if p.pid != a)
    g.send(a, g.players[a].pawns[0].uid, e.eid)
    g.send(b, g.players[b].pawns[0].uid, e.eid)
    return g, e, a, b


def contest_for(g, e, stances):
    g.contest = {"env": e.eid, "players": list(stances), "stances": stances}
    g.report = {"awards": [], "rolls": [], "rerolls": 0, "text": "", "wounds": []}
    g.tie_note = ""


def test_noble_fights_and_is_worth_4_vp():
    g, e, a, b = duel()
    g.players[a].pawns[0].kind = "noble"
    assert D.pawn_vp("noble") == 4
    assert g.strength(a, e.eid, False) == 2


def test_merchant_costs_9_and_is_worth_2_vp():
    assert D.PAWNS["merchant"]["cost"] == 9 and D.pawn_vp("merchant") == 2


def test_thief_steals_nothing_from_a_single_item_prize():
    g, e, a, b = duel(prize=("wood", 1))
    g.players[a].pawns[0].kind = "thief"
    contest_for(g, e, {a: (FIGHT, None), b: (FIGHT, None)})
    g._settle = lambda rolls, mob: next(r for r in rolls if r["pid"] == b)
    g._resolve_fight(e, [a, b], {a: 0, b: 0})
    assert g.report["awards"] == [(b, "wood", 1)]


def test_thief_steals_one_from_a_two_item_prize():
    g, e, a, b = duel(prize=("wood", 2))
    g.players[a].pawns[0].kind = "thief"
    contest_for(g, e, {a: (FIGHT, None), b: (FIGHT, None)})
    g._settle = lambda rolls, mob: next(r for r in rolls if r["pid"] == b)
    g._resolve_fight(e, [a, b], {a: 0, b: 0})
    assert sorted(g.report["awards"]) == sorted([(b, "wood", 1), (a, "wood", 1)])


def alchemy_game():
    g = new_game(2, seed=3)
    a = g.active
    p = g.players[a]
    p.pawns[0].kind = "alchemist"
    p.res.update(pearl=1, amber=1, herbs=2)
    play_to_actions(g)
    while g.active != a:
        g.end_actions(g.active)
    return g, a, p


def other_target(target):
    return "mithril" if target == "crystal" else "crystal"


@pytest.mark.parametrize("target,source", [("crystal", "amber"), ("mithril", "pearl")])
def test_alchemist_turns_one_resource_into_its_pair(target, source):
    g, a, p = alchemy_game()
    other = "pearl" if source == "amber" else "amber"
    before = p.res[target]
    g.transmute(a, target)
    assert p.res[target] == before + 1
    assert p.res[source] == 0 and p.res[other] == 1
    assert p.pawns[0].brewed and not p.pawns[0].used  # it can still build
    with pytest.raises(GameError):
        g.transmute(a, other_target(target))


def test_alchemist_needs_the_matching_resource():
    g, a, p = alchemy_game()
    p.res["amber"] = 0
    with pytest.raises(GameError):
        g.transmute(a, "crystal")
    g.transmute(a, "mithril")
    assert p.res["mithril"] >= 1


def test_alchemist_only_makes_crystal_or_mithril():
    g, a, p = alchemy_game()
    with pytest.raises(GameError):
        g.transmute(a, "relic")


def test_computer_alchemist_cashes_in_when_it_pays(monkeypatch):
    g, a, p = alchemy_game()
    monkeypatch.setattr(ai, "plan_scores", lambda game, pid: {b: -1 for b in D.BUILDINGS})
    g.prices.update(amber=3, crystal=7, pearl=5, mithril=5)
    assert ai._alchemy_target(g, a) == "crystal"
    g.prices.update(amber=5, crystal=5)
    assert ai._alchemy_target(g, a) is None


def test_kept_pawn_is_named_in_the_log():
    g = new_game(2)
    a = g.active
    pawn = g.players[a].pawns[0]
    g.keep_home(a, pawn.uid)
    assert pawn.placed and pawn.location == HOME
    assert any(f"{pawn.name} stays home" in line for line in g.logs)


def test_done_placing_names_the_pawns_that_stay():
    g = new_game(2)
    a = g.active
    p = g.players[a]
    g.done_placing(a)
    assert all(x.placed for x in p.pawns)
    assert any(p.name in line and "stay home" in line and p.pawns[0].name in line for line in g.logs)


def test_prizes_always_match_the_zone_list_even_with_a_strong_mob():
    for seed in range(60):
        g = new_game(2, seed=seed)
        g.turn = 7
        g.reveal_all()
        for e in g.envs:
            allowed = [q for _, q in D.ENVIRONMENTS[e.eid]["prizes"]]
            assert e.prize[1] in allowed


def test_every_fighter_on_the_losing_side_misses_next_turn():
    g = new_game()
    e = g.envs[0]
    e.mob, e.prize = None, ("crystal", 1)
    a, b = g.active, 1 - g.active
    g.send(a, g.players[a].pawns[0].uid, e.eid)
    g.send(b, g.players[b].pawns[0].uid, e.eid)
    g.send(a, g.players[a].pawns[1].uid, e.eid)
    g.send(b, g.players[b].pawns[1].uid, e.eid)
    while g.phase == "actions":
        g.end_actions(g.active)
    g.harvest_next()
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    loser = 0 if g.players[1].res["crystal"] else 1
    assert len(g.report["wounds"]) == 2
    while g.phase == "harvest":
        g.ack_report() if g.harvest_stage == "report" else g.harvest_next()
    assert all(x.resting for x in g.players[loser].pawns)
    assert not any(x.resting for x in g.players[1 - loser].pawns)


def test_knight_and_healer_protect_from_a_lost_fight():
    g, e = setup_contest(mob=("Boss", 50))
    p = g.players[g.active]
    p.pawns[0].kind = "knight"
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    assert [w for w in g.report["wounds"] if w[0] == p.pid] == []


def test_building_needs_its_requirement():
    g = new_game()
    to_actions(g)
    a = g.active
    p = g.players[a]
    p.res.update({"wood": 9, "food": 9, "stone": 9})
    allowed, reason = g.can_build(a, "herb_garden")
    assert not allowed and reason == "Needs Farm"
    g.build(a, "farm")
    assert g.can_build(a, "herb_garden")[0]


def test_tree_is_valid_and_castle_is_hardest():
    for bid, info in D.BUILDINGS.items():
        for need in D.requirements(bid):
            assert D.BUILDINGS[need]["tier"] < info["tier"]
        assert bool(D.requirements(bid)) == (info["tier"] > 1)
    price = lambda b: sum(D.RESOURCES[r][1] * n for r, n in D.BUILDINGS[b]["cost"].items())
    assert max(D.BUILDINGS, key=price) == "castle"


@pytest.mark.parametrize("tier4", ["temple", "guild_hall", "bank", "trophy_hall"])
def test_any_tier_4_building_unlocks_the_castle(tier4):
    g = new_game()
    to_actions(g)
    a = g.active
    p = g.players[a]
    p.res.update({"stone": 9, "iron": 9, "crystal": 9, "mithril": 9})
    allowed, reason = g.can_build(a, "castle")
    assert not allowed and " or " in reason
    p.buildings.append(tier4)
    assert g.can_build(a, "castle")[0]


def test_every_pawn_gives_plus_one_and_breakdown_adds_up():
    g = new_game()
    a = g.active
    p = g.players[a]
    e = g.envs[0]
    p.pawns[0].kind = "knight"
    p.buildings = ["barracks", "training_ground"]
    g.send(a, p.pawns[0].uid, e.eid)
    g.done_placing(g.active)
    g.send(a, p.pawns[1].uid, e.eid)
    parts = dict(g.strength_parts(a, e.eid, True))
    assert parts["2 pawns"] == 2 and parts["Lancer"] == 3
    assert parts["Barracks"] == 1 and parts["Training Ground"] == 1
    assert g.strength(a, e.eid, True) == 7


def lone_stacks(g):
    """Computer stacks of 3+ on a place with no mob and no other player."""
    found = []
    for e in g.envs:
        present = g.visitors_now(e.eid)
        if not e.mob and len(present) == 1 and len(g.pawns_at(present[0], e.eid)) > 2:
            found.append(e.eid)
    return found


@pytest.mark.parametrize("seed", range(25))
def test_computer_does_not_stack_on_a_quiet_place(seed):
    g = new_game(2, turns=12, seed=seed, is_ai=True)
    while g.phase != "end":
        if g.phase == "harvest" and g.harvest_stage == "next":
            full = all(len(g.pawns_at(p, e.eid)) >= 2 or e.mob or len(g.visitors_now(e.eid)) > 1
                       for p in range(2) for e in g.envs)
            assert not lone_stacks(g) or full
            g.harvest_next()
        elif g.phase == "harvest" and g.harvest_stage == "report":
            g.ack_report()
        else:
            ai.play_step(g)


def test_game_length_picks_its_own_trained_player(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(ai, "TRAINED_FILE", str(tmp_path / "trained_ai.json"))
    (tmp_path / "trained_ai_8.json").write_text(json.dumps({"weights": {"tier": 8.0}}))
    (tmp_path / "trained_ai.json").write_text(json.dumps({"weights": {"tier": 1.0}}))
    assert ai.load_trained(ai.trained_path(8))["tier"] == 8.0
    assert ai.load_trained(ai.trained_path(10)) is None
    assert ai.load_trained(str(tmp_path / "trained_ai.json"))["tier"] == 1.0


def test_trained_weights_are_used_and_finish_a_game():
    g = new_game(2, seed=3, is_ai=True)
    g.brains[0] = {**ai.DEFAULT_WEIGHTS, "variety": 0, "town_stock": 1, "fight_margin": 0}
    run_ai_game(g)
    assert g.final


def test_victory_points():
    assert D.pawn_vp("peasant") == 0
    assert all(1 <= D.pawn_vp(k) <= 4 for k in D.PAWNS if k != "peasant" and k not in D.FACTION_PAWNS)
    strongest = {"panda", "oar_shark", "skull_shaman", "dwarf_builder"}
    for k in D.FACTION_PAWNS:
        assert D.pawn_vp(k) == (0 if k == "raider" else 2 if k in strongest else 1), k
    assert D.pawn_vp("farmer") == 1 and D.pawn_vp("mage") == 2 and D.pawn_vp("champion") == 3
    g = new_game(turns=1)
    p = g.players[0]
    p.buildings = ["farm", "castle"]
    p.pawns[0].kind = "noble"
    p.res = {r: 0 for r in p.res}
    p.gold = 14
    g._finish()
    lines = dict(next(r for r in g.final if r["pid"] == 0)["lines"])
    assert lines == {"Buildings": 37, "Pawns": 4, "Gold": 2}
    assert next(r for r in g.final if r["pid"] == 0)["total"] == 43


def test_unsold_resources_count_as_gold_before_conversion():
    g = new_game(turns=1)
    p = g.players[0]
    p.res = {r: 0 for r in p.res}
    p.res["relic"] = 2
    p.gold = 4
    assert g.victory_points(0)[2:4] == (12, 2)


@pytest.mark.parametrize("building", list(D.BUILDINGS))
def test_building_beats_selling_its_materials(building):
    sold = sum(D.top_price(r) * n for r, n in D.BUILDINGS[building]["cost"].items())
    assert D.building_vp(building) * D.GOLD_PER_VP > sold


def test_prices_stay_within_the_top_price():
    for seed in range(50):
        g = new_game(seed=seed)
        for r, price in g.prices.items():
            assert 1 <= price <= D.top_price(r)


def setup_contest(n=2, mob=None, prize=("crystal", 2)):
    g = new_game(n)
    e = g.envs[0]
    e.mob, e.prize, e.harvest = mob, prize, ["wood", "wood"]
    for pid in g.order():
        pass
    while g.phase == "deploy":
        a = g.active
        pawns = g.deployable(a)
        if a < n and pawns and not g.pawns_at(a, e.eid):
            g.send(a, pawns[0].uid, e.eid)
        else:
            g.done_placing(a)
    while g.phase == "actions":
        g.end_actions(g.active)
    g.harvest_next()
    return g, e


def test_only_one_pawn_per_player_in_town():
    g = new_game()
    a, b = g.active, 1 - g.active
    g.send(a, g.players[a].pawns[0].uid, TOWN)
    g.send(b, g.players[b].pawns[0].uid, TOWN)
    with pytest.raises(GameError):
        g.send(a, g.players[a].pawns[1].uid, TOWN)
    assert g.active == a and g.players[a].pawns[1].location == HOME


def test_split_is_equal_and_the_rest_is_lost():
    g, e = setup_contest(prize=("crystal", 3))
    for _ in range(2):
        g.set_stance(g.active, SPLIT)
    assert g.players[0].res["crystal"] == 1 and g.players[1].res["crystal"] == 1


def test_one_item_split_between_two_is_lost():
    g, e = setup_contest(prize=("wood", 1))
    before = [p.res["wood"] for p in g.players]
    for _ in range(2):
        g.set_stance(g.active, SPLIT)
    assert [p.res["wood"] for p in g.players] == before
    assert g.report["awards"] == []


def test_tied_players_roll_again_until_one_wins():
    g, e = setup_contest()
    rolls = iter([[3], [3], [2], [2], [5], [1]])
    g._roll = lambda n: next(rolls)
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    assert g.report["rerolls"] == 2
    scores = sorted(r["score"] for r in g.report["rolls"])
    assert scores[0] != scores[1]
    assert "rolled again" in g.report["text"]


def test_tie_with_a_mob_is_rolled_again():
    g, e = setup_contest(mob=("Test", 1))
    a = g.active
    rolls = iter([[4], [4], [1], [6], [1]])  # mob, A, B, then mob and A again
    g._roll = lambda n: next(rolls)
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    assert g.report["rerolls"] == 1
    assert g.report["mob"]["score"] == g.report["mob"]["die"] + 1
    assert g.report["mob"]["score"] != max(r["score"] for r in g.report["rolls"])


def test_no_dice_when_nobody_contests_the_prize():
    g, e = setup_contest()
    a, b = g.active, 1 - g.active
    g.set_stance(a, YIELD)
    g.set_stance(b, FIGHT)
    assert g.report["rolls"] == [] and g.players[b].res["crystal"] == 2


def test_two_players_split():
    g, e = setup_contest()
    for _ in range(2):
        g.set_stance(g.active, SPLIT)
    assert g.harvest_stage == "report"
    assert g.players[0].res["crystal"] == 1 and g.players[1].res["crystal"] == 1


def labels(g):
    return [label for _, _, label in g.stance_options(g.active)]


def test_first_player_can_fight_split_or_retreat():
    g, e = setup_contest()
    assert labels(g) == ["Fight for it", "Propose a split", "Retreat"]  # no more "Give it to"


def test_after_a_fight_the_next_player_cannot_split():
    g, e = setup_contest()
    g.set_stance(g.active, FIGHT)
    assert labels(g) == ["Fight for it", "Retreat"]
    with pytest.raises(GameError):
        g.set_stance(g.active, SPLIT)


def test_after_a_split_the_next_player_can_still_split():
    g, e = setup_contest()
    g.set_stance(g.active, SPLIT)
    assert labels(g) == ["Fight for it", "Propose a split", "Retreat"]


def split_against_mob(scores):
    """Both players split in front of a mob that scores 4 (die 1 + 3)."""
    g, e = setup_contest(mob=("Test", 3), prize=("crystal", 2))
    order = [g.active, 1 - g.active]
    dice = iter([[1]] + [[scores[pid] - 1] for pid in g.contest["players"]])
    g._roll = lambda n: next(dice)
    for _ in order:
        g.set_stance(g.active, SPLIT)
    return g


def test_split_against_a_mob_both_winners_share():
    g = split_against_mob({0: 6, 1: 7})
    assert g.players[0].res["crystal"] == 1 and g.players[1].res["crystal"] == 1
    assert not g.report["wounds"]


def test_split_against_a_mob_only_the_winner_takes_it():
    g = split_against_mob({0: 6, 1: 3})
    assert g.players[0].res["crystal"] == 2 and g.players[1].res["crystal"] == 0
    assert [pid for pid, _ in g.report["wounds"]] == [1]


def test_split_against_a_mob_nobody_wins():
    g = split_against_mob({0: 2, 1: 3})
    assert g.players[0].res["crystal"] == 0 and g.players[1].res["crystal"] == 0
    assert len(g.report["wounds"]) == 2


def test_fight_gives_prize_to_one_player():
    g, e = setup_contest()
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    assert sorted([g.players[0].res["crystal"], g.players[1].res["crystal"]]) == [0, 2]
    assert len(g.report["rolls"]) == 2


def test_score_is_die_plus_pawns():
    g, e = setup_contest(mob=("Test", 1))
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    for roll in g.report["rolls"]:
        assert roll["strength"] == 1
        assert roll["score"] == max(roll["dice"]) + 1


def test_mob_wins_ties_and_wounds_pawn():
    g, e = setup_contest(mob=("Boss", 50))
    g.set_stance(g.active, FIGHT)
    g.set_stance(g.active, FIGHT)
    assert g.players[0].res["crystal"] == 0 and g.players[1].res["crystal"] == 0
    assert len(g.report["wounds"]) == 2
    g.ack_report()
    assert g.turn == 2
    assert any(x.resting for x in g.players[0].pawns)
    pid = g.active
    assert all(not x.resting for x in g.deployable(pid))


def test_retreat_avoids_mob():
    g = new_game()
    e = g.envs[0]
    e.mob = ("Boss", 50)
    a = g.active
    g.send(a, g.players[a].pawns[0].uid, e.eid)
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.phase == "actions":
        g.end_actions(g.active)
    g.harvest_next()
    g.set_stance(a, YIELD, None)
    assert not g.report["wounds"] and not g.report["awards"]


def test_alone_without_mob_gets_prize():
    g = new_game()
    e = g.envs[0]
    e.mob, e.prize = None, ("gold", 5)
    a = g.active
    p = g.players[a]
    g.send(a, p.pawns[0].uid, e.eid)
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.phase == "actions":
        g.end_actions(g.active)
    gold = p.gold
    g.harvest_next()
    assert p.gold == gold + 5
    assert g.report["rolls"] == [] and g.harvest_stage == "report"


def test_abilities_affect_strength_and_harvest():
    g = new_game()
    a = g.active
    p = g.players[a]
    e = g.envs[0]
    e.harvest = ["wood", "wood"]
    p.pawns[0].kind = "knight"
    p.pawns[1].kind = "lumberjack"
    p.buildings.append("barracks")
    g.send(a, p.pawns[0].uid, e.eid)
    g.done_placing(g.active)
    g.send(a, p.pawns[1].uid, e.eid)
    assert g.strength(a, e.eid, True) == 2 + 3 + 1


def test_every_data_reference_is_valid():
    for b in D.BUILDINGS.values():
        for r in list(b["cost"]) + list(b.get("produce", {})):
            assert r in D.RESOURCES
    for e in D.ENVIRONMENTS.values():
        assert all(r in D.RESOURCES for r in e["harvest"])
        assert all(r == "gold" or r in D.RESOURCES for r, _ in e["prizes"])
    assert len(D.BUILDINGS) >= 20 and len(D.PAWNS) >= 20


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("n", [2, 3, 4])
def test_full_games_finish_with_legal_state(seed, n):
    g = new_game(n, seed=seed, is_ai=True)
    run_ai_game(g)
    assert g.final and len(g.final) == n
    for p in g.players:
        assert p.gold >= 0 and all(v >= 0 for v in p.res.values())
        assert len(p.pawns) <= g.pawn_limit(p.pid) and len(p.buildings) <= D.MAX_BUILDINGS


# ---- zone events ---------------------------------------------------------
def zone_game(eid, event, players=2, seed=5):
    """A game whose zone `eid` is on the table and has this event."""
    for s in range(seed, seed + 500):
        g = new_game(players, seed=s)
        if any(e.eid == eid for e in g.envs):
            g.events[eid] = event
            return g, g.env(eid)
    raise AssertionError("zone never drawn")


def to_zone(g, pid, env, count=1):
    """Send this player's pawns straight to a zone, ignoring turn order."""
    pawns = g.players[pid].pawns
    while len(pawns) < count:
        g.add_pawn(pid, "peasant")
    for pawn in pawns[:count]:
        pawn.location = env.eid
        pawn.placed = True
        g.arrivals += 1
        pawn.arrival = g.arrivals
    return pawns[:count]


def collect(g, env):
    g.phase = "harvest"
    g.harvest_queue = [env.eid]
    g.harvest_stage = "next"
    g.harvest_next()
    return g.report


def gain(report, pid, name):
    return [(r, q) for p, r, q, who in report["gathers"] if p == pid and who == name]


def test_events_are_off_by_default():
    assert new_game().events == {}


def test_every_zone_gets_one_event_with_one_disaster_at_most():
    seen = set()
    for seed in range(300):
        g = Game([("a", False), ("b", False), ("c", False), ("d", False)], seed=seed, events=True)
        assert set(g.events) == {e.eid for e in g.envs} | {TOWN}
        assert sum(k in D.RARE_DISASTERS for k in g.events.values()) <= 1
        seen.update(g.events.values())
    assert seen == {k for zone in D.ZONE_EVENTS.values() for k in zone}


def test_events_stay_for_the_whole_game():
    g = Game([("a", True), ("b", True)], turns=4, seed=2, events=True)
    start = dict(g.events)
    while g.phase != "end":
        if g.phase == "harvest" and g.harvest_stage == "next":
            g.harvest_next()
        elif g.phase == "harvest" and g.harvest_stage == "report":
            g.ack_report()
        else:
            ai.play_step(g)
    assert g.events == start


@pytest.mark.parametrize("seed", range(8))
def test_computer_players_finish_games_with_events(seed):
    for players in (2, 3, 4):
        g = Game([(str(i), True) for i in range(players)], turns=10, seed=seed, events=True)
        while g.phase != "end":
            if g.phase == "harvest" and g.harvest_stage == "next":
                g.harvest_next()
            elif g.phase == "harvest" and g.harvest_stage == "report":
                g.ack_report()
            else:
                ai.play_step(g)


@pytest.mark.parametrize("eid,event,res,extra", [
    ("forest", "wild_berries", "wood", ("food", 1)),
    ("forest", "sacred_grove", "food", ("wood", 1)),
    ("mountain", "crystal_caves", "iron", ("stone", 1)),
    ("mine", "ancient_machinery", "iron", ("stone", 1)),
    ("mine", "rich_iron_vein", "stone", ("iron", 1)),
    ("mine", "rich_stone_vein", "iron", ("stone", 1)),
    ("plains", "good_harvest", "food", ("food", 1)),
    ("plains", "good_harvest", "wood", ("wood", 1)),
    ("plains", "fertile_fields", "food", ("food", 2)),
    ("mine", "prospectors_claim", "stone", ("iron", 1)),
])
def test_gathering_events(eid, event, res, extra):
    g, env = zone_game(eid, event)
    env.harvest = [res]
    env.mob = None
    to_zone(g, 0, env)
    report = collect(g, env)
    assert gain(report, 0, D.ZONE_EVENTS[eid][event][0]) == [extra]


def test_wild_berries_needs_wood_and_is_per_player():
    g, env = zone_game("forest", "wild_berries")
    env.harvest = ["food"]
    env.mob = None
    to_zone(g, 0, env, 3)
    assert gain(collect(g, env), 0, "Wild Berries") == []
    g, env = zone_game("forest", "wild_berries")
    env.harvest = ["wood"]
    env.mob = None
    to_zone(g, 0, env, 3)
    assert gain(collect(g, env), 0, "Wild Berries") == [("food", 1)]


def test_sacred_grove_needs_exactly_one_pawn():
    g, env = zone_game("forest", "sacred_grove")
    env.mob = None
    to_zone(g, 0, env)
    to_zone(g, 1, env, 2)
    report = collect(g, env)
    assert gain(report, 0, "Sacred Grove") == [("wood", 1)]
    assert gain(report, 1, "Sacred Grove") == []


def test_prospector_tie_gives_nothing():
    g, env = zone_game("mine", "prospectors_claim")
    to_zone(g, 0, env, 2)
    to_zone(g, 1, env, 2)
    report = collect(g, env)
    assert gain(report, 0, "Prospector's Claim") == gain(report, 1, "Prospector's Claim") == []


def test_good_fishing_gives_one_food_per_player():
    g, env = zone_game("lake", "good_fishing")
    env.harvest = ["food"]
    env.mob = None
    env.prize = ("food", 3)
    to_zone(g, 0, env, 3)
    report = collect(g, env)
    assert gain(report, 0, "Good Fishing") == [("food", 1)]
    assert report["awards"] == [(0, "food", 3)]


@pytest.mark.parametrize("eid,event,res", [("lake", "golden_fish", "food"), ("mine", "gold_nugget", "stone")])
def test_event_dice_are_reported(eid, event, res):
    g, env = zone_game(eid, event)
    env.harvest = [res]
    env.mob = None
    to_zone(g, 0, env)
    g.rng.randint = lambda a, b: 6
    report = collect(g, env)
    assert report["event_dice"][0][:4] == (0, D.ZONE_EVENTS[eid][event][0], 6, True)


def test_disaster_die_is_shown_even_when_nothing_happens():
    g, env = zone_game("forest", "forest_fire")
    env.mob = None
    to_zone(g, 0, env)
    g.rng.randint = lambda a, b: 4
    report = collect(g, env)
    assert report["event_dice"] == [(None, "Forest Fire", 4, True, "nothing happens (only a 1 strikes)")]
    assert not g.choices


def test_deep_waters_needs_two_pawns():
    g, env = zone_game("lake", "deep_waters")
    env.harvest = ["food"]
    env.mob = None
    to_zone(g, 0, env, 2)
    assert gain(collect(g, env), 0, "Deep Waters") == [("food", 2)]
    g, env = zone_game("lake", "deep_waters")
    env.harvest = ["food"]
    env.mob = None
    to_zone(g, 0, env, 1)
    assert gain(collect(g, env), 0, "Deep Waters") == []


@pytest.mark.parametrize("eid,event,qty", [("lake", "golden_fish", 2), ("mine", "gold_nugget", 3)])
def test_lucky_die_events_pay_on_a_six(eid, event, qty):
    g, env = zone_game(eid, event)
    env.harvest = ["food"]
    env.mob = None
    to_zone(g, 0, env)
    g.rng.randint = lambda a, b: 6
    assert gain(collect(g, env), 0, D.ZONE_EVENTS[eid][event][0]) == [("gold", qty)]


def test_high_ground_and_swamp_gas_and_narrow_pass():
    g, env = zone_game("mountain", "high_ground")
    to_zone(g, 0, env, 3)
    assert g.strength(0, env.eid, False) == 6
    g, env = zone_game("swamp", "swamp_gas")
    pawns = to_zone(g, 0, env, 2)
    pawns[0].kind = "warrior"
    assert g.strength(0, env.eid, False) == 3  # Warrior 3 - 1, Peasant stays 1
    g, env = zone_game("mountain", "narrow_pass")
    pawns = to_zone(g, 0, env, 3)
    pawns[2].kind = "champion"
    assert g.strength(0, env.eid, False) == 2


def test_open_ground_ignores_buildings():
    g, env = zone_game("plains", "open_ground")
    g.players[0].buildings = ["armory", "watchtower", "training_ground"]
    to_zone(g, 0, env)
    assert g.strength(0, env.eid, False) == 1


def test_quicksand_allows_two_pawns():
    g, env = zone_game("swamp", "quicksand")
    to_zone(g, 0, env, 2)
    assert not g.can_send(0, env.eid)[0]
    assert g.can_send(1, env.eid)[0]
    assert g.can_send(0, g.envs[0].eid if g.envs[0] is not env else g.envs[1].eid)[0]


def test_computer_respects_quicksand():
    g, env = zone_game("swamp", "quicksand")
    to_zone(g, 0, env, 2)
    assert env not in ai.env_choices(g, 0)


def test_healing_mud_stops_wounds():
    g, env = zone_game("swamp", "healing_mud")
    to_zone(g, 0, env, 2)
    assert g.woundable(0, env.eid) == []


def strike(g, env):
    """Force the zone's disaster to happen."""
    g.rng.randint = lambda a, b: 1
    return collect(g, env)


@pytest.mark.parametrize("eid,event", [("forest", "forest_fire"), ("mountain", "avalanche"),
                                       ("swamp", "plague")])
def test_disaster_lets_the_player_choose_who_is_wounded(eid, event):
    g, env = zone_game(eid, event)
    env.mob = None
    pawns = to_zone(g, 0, env, 2)
    pawns[0].kind = "warrior"
    strike(g, env)
    g.ack_report()
    assert g.harvest_stage == "choice" and g.active == 0
    assert len(g.choice_options()) == 2
    g.choose(0, pawns[1].uid)
    assert pawns[1].resting and not pawns[0].resting


def test_disaster_with_one_kind_of_pawn_needs_no_choice():
    g, env = zone_game("forest", "forest_fire")
    env.mob = None
    pawns = to_zone(g, 0, env, 2)
    strike(g, env)
    g.ack_report()
    assert g.harvest_stage != "choice"
    assert sum(x.resting for x in pawns) == 1


def test_disaster_spares_tough_pawns():
    g, env = zone_game("forest", "forest_fire")
    env.mob = None
    pawns = to_zone(g, 0, env, 1)
    pawns[0].kind = "knight"
    strike(g, env)
    g.ack_report()
    assert not pawns[0].resting


def test_territorial_animals_holds_one_of_three_pawns():
    g, env = zone_game("forest", "territorial_animals")
    env.mob = None
    pawns = to_zone(g, 0, env, 3)
    pawns[0].kind = "knight"
    collect(g, env)
    g.ack_report()
    g.choose(0, pawns[0].uid)
    assert pawns[0].resting and pawns[0].stuck  # even a Lancer is left behind


def test_left_behind_pawn_misses_next_turn():
    g, env = zone_game("forest", "territorial_animals")
    pawn = g.players[0].pawns[0]
    pawn.stuck_next = True
    g.start_turn()
    assert pawn.resting and pawn.stuck
    g.start_turn()
    assert not pawn.resting and not pawn.stuck


def test_mountain_shrine_pays_after_a_fight_only():
    g, env = zone_game("mountain", "mountain_shrine")
    env.mob = None
    env.prize = ("iron", 1)
    to_zone(g, 0, env)
    assert (0, "gold", 2) not in collect(g, env)["awards"]
    g, env = zone_game("mountain", "mountain_shrine")
    env.mob = ("Gnolls", 0)
    env.prize = ("iron", 1)
    to_zone(g, 0, env, 3)
    collect(g, env)
    g.tie_note = ""
    g._settle = lambda rolls, mob: rolls[0]
    g.set_stance(0, FIGHT)
    assert (0, "gold", 2) in g.report["awards"]


@pytest.mark.parametrize("eid,event", [("swamp", "sunken_treasure"), ("ruins", "forgotten_treasury")])
def test_treasure_events_add_gold_to_the_prize(eid, event):
    g, env = zone_game(eid, event)
    env.mob = None
    env.prize = ("wood", 2)
    to_zone(g, 0, env)
    assert sorted(collect(g, env)["awards"], key=str) == sorted([(0, "gold", 2), (0, "wood", 2)], key=str)


def test_curse_takes_a_gold_if_there_is_one():
    g, env = zone_game("ruins", "curse")
    env.mob = None
    env.prize = ("wood", 1)
    p = g.players[0]
    to_zone(g, 0, env)
    before = p.gold
    collect(g, env)
    assert p.gold == before - 1
    g, env = zone_game("ruins", "curse")
    env.mob = None
    env.prize = ("wood", 1)
    p = g.players[0]
    p.gold = 0
    to_zone(g, 0, env)
    collect(g, env)
    assert p.gold == 0


def test_trapped_relic_can_lose_the_prize():
    g, env = zone_game("ruins", "trapped_relic")
    env.mob = None
    to_zone(g, 0, env)
    g.rng.randint = lambda a, b: 1
    assert collect(g, env)["awards"] == []


def test_cursed_treasure_is_a_choice():
    g, env = zone_game("ruins", "cursed_treasure")
    env.mob = None
    env.prize = ("wood", 1)
    pawns = to_zone(g, 0, env, 1)
    p = g.players[0]
    p.gold = 5
    collect(g, env)
    g.ack_report()
    assert [v for v, _ in g.choice_options()] == ["pay", pawns[0].uid]
    g.choose(0, "pay")
    assert p.gold == 3 and not pawns[0].wounded_next


def test_cursed_treasure_without_gold_wounds():
    g, env = zone_game("ruins", "cursed_treasure")
    env.mob = None
    env.prize = ("wood", 1)
    pawns = to_zone(g, 0, env, 1)
    g.players[0].gold = 1
    collect(g, env)
    g.ack_report()
    assert pawns[0].resting and g.players[0].gold >= 1


def test_ancient_knowledge_and_trade_route_reward_the_first_player():
    g, env = zone_game("ruins", "ancient_knowledge")
    a = g.active
    g.send(a, g.players[a].pawns[0].uid, env.eid)
    assert g.strength(a, env.eid, False) == 2
    g, env = zone_game("plains", "trade_route")
    a = g.active
    b = next(p.pid for p in g.players if p.pid != a)
    gold = g.players[a].gold, g.players[b].gold
    g.send(a, g.players[a].pawns[0].uid, env.eid)
    g.send(b, g.players[b].pawns[0].uid, env.eid)
    assert g.players[a].gold == gold[0] + 1 and g.players[b].gold == gold[1]


def test_friendly_monster_joins_the_first_player():
    g, env = zone_game("plains", "friendly_monster")
    env.mob = ("Snakes", 3)
    a = g.active
    b = next(p.pid for p in g.players if p.pid != a)
    g.send(a, g.players[a].pawns[0].uid, env.eid)
    g.send(b, g.players[b].pawns[0].uid, env.eid)
    assert env.mob is None
    assert g.strength(a, env.eid, False) == 4 and g.strength(b, env.eid, False) == 1
    env.harvest = ["wood"]
    collect(g, env)
    assert [x[2] for x in g.report["gathers"]] == [1, 1]  # the monster collects nothing


@pytest.mark.parametrize("eid,event", [("lake", "abundance"), ("plains", "migrating_herds")])
def test_food_can_join_the_prize(eid, event):
    g, env = zone_game(eid, event)
    g.rng.randrange = lambda n: 0
    g.rng.randint = lambda a, b: 6
    g.turn = 1
    g.reveal_all()
    assert env.extra_food == 1
    env.mob = None
    env.prize = ("gold", 3)
    to_zone(g, 0, env)
    report = collect(g, env)
    assert (0, "food", 1) in report["awards"] and (0, "gold", 3) in report["awards"]


def test_fog_hides_the_monster_until_pawns_are_placed():
    g, env = zone_game("swamp", "fog")
    env.mob = ("Spiders", 5)
    prize = env.prize[1]
    assert g.mob_hidden(env) and g.known_mob(env) is None
    while g.phase == "deploy":
        g.done_placing(g.active)
    assert g.known_mob(env) == ("Spiders", 5)
    assert env.prize[1] == prize


def test_market_events():
    g = new_game()
    g.events[TOWN] = "market_tax"
    g.players[0].res["wood"] = 5
    assert g.sale_value(0, {"wood": 3}) == 1
    assert g.sale_value(0, {"wood": 1}) == 0
    g.events[TOWN] = "traveling_merchant"
    assert g.sale_value(0, {"relic": 1}) == 12
    g.relic_sold = True
    assert g.sale_value(0, {"relic": 1}) == g.prices["relic"]
    g.events[TOWN] = "holy_grail"
    g.start_turn()
    assert g.prices["relic"] == 10


def test_wandering_hero_gives_everyone_the_same_pawn():
    for seed in range(200):
        g = Game([("a", False), ("b", False)], seed=seed, events=True)
        if g.events[TOWN] == "wandering_hero":
            assert all(len(p.pawns) == 3 and p.pawns[2].kind == g.hero for p in g.players)
            return
    raise AssertionError("never drawn")


# ---- full roster ---------------------------------------------------------
def full_roster():
    g = new_game(2)
    a = g.active
    p = g.players[a]
    while len(p.pawns) < D.MAX_PAWNS:
        g.add_pawn(a, "peasant")
    p.gold = 50
    g.send(a, p.pawns[0].uid, TOWN)
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.active != a:
        g.end_actions(g.active)
    g.recruits[a][1] = "warrior"
    return g, a, p


def test_full_roster_can_recruit_by_dismissing_a_pawn():
    g, a, p = full_roster()
    leaving = p.pawns[1]
    assert g.must_dismiss(a) and g.can_recruit(a, 1)[0]
    g.recruit(a, 1, leaving.uid)
    assert len(p.pawns) == D.MAX_PAWNS + 1 and len(g.staying(a)) == D.MAX_PAWNS
    assert leaving.leaving and p.pawns[-1].kind == "warrior"
    g._end_turn()
    assert len(p.pawns) == D.MAX_PAWNS and leaving not in p.pawns


def test_a_replaced_pawn_cannot_be_chosen_twice_and_stops_counting_for_vp():
    g, a, p = full_roster()
    leaving = p.pawns[1]
    before = g.victory_points(a)[1]
    g.recruit(a, 1, leaving.uid)
    assert leaving not in g.dismissable(a)
    assert g.victory_points(a)[1] == before - g.pawn_points(leaving) + g.pawn_points(p.pawns[-1])


def test_replacing_on_the_last_turn_gives_no_extra_pawn():
    g, a, p = full_roster()
    leaving = p.pawns[1]
    g.max_turns = g.turn
    g.recruit(a, 1, leaving.uid)
    g._end_turn()
    assert g.phase == "end" and leaving not in p.pawns and len(p.pawns) == D.MAX_PAWNS


def test_the_peasant_of_the_house_can_be_replaced():
    g, a, p = full_roster()
    peasant = g.pawns_at(a, HOME)[-1]
    peasant.kind = "peasant"
    p.pawns.remove(peasant)
    g.add_pawn(a, "peasant")
    house_peasant = p.pawns[-1]
    assert house_peasant in g.dismissable(a)
    g.recruit(a, 1, house_peasant.uid)
    assert house_peasant.leaving


def test_town_never_offers_the_same_pawn_twice():
    for seed in range(200):
        g = new_game(seed=seed)
        g._start_actions()
        offers = g.recruits[0]
        assert offers[0] == "peasant" and len(set(offers)) == len(offers) == 1 + D.RECRUITS_PER_TURN


def test_full_roster_needs_a_pawn_to_dismiss():
    g, a, p = full_roster()
    gold = p.gold
    with pytest.raises(GameError):
        g.recruit(a, 1)
    assert p.gold == gold and g.recruits[a][1] == "warrior"


def test_the_recruiter_in_town_can_be_replaced_too():
    g, a, p = full_roster()
    recruiter = g.pawns_at(a, TOWN)[0]
    assert recruiter in g.dismissable(a)
    g.recruit(a, 1, recruiter.uid)
    assert recruiter.leaving and len(g.staying(a)) == g.pawn_limit(a)


def test_dismissing_is_not_needed_below_the_limit():
    g, a, p = full_roster()
    p.pawns.pop(1)
    g.recruit(a, 1)
    assert len(p.pawns) == D.MAX_PAWNS


def test_computer_never_dismisses_and_stays_at_the_limit():
    g, a, p = full_roster()
    assert ai.best_recruit(g, a)[0] is None


def full_house():
    g = new_game(2)
    a = g.active
    p = g.players[a]
    while len(p.pawns) < D.MAX_PAWNS:
        g.add_pawn(a, "peasant")
    p.pawns[1].kind = "warrior"
    p.res.update({r: 20 for r in p.res})
    p.buildings = list(D.requirements("house"))
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.active != a:
        g.end_actions(g.active)
    return g, a, p


def test_full_house_can_replace_a_pawn_with_the_free_peasant():
    g, a, p = full_house()
    warrior = p.pawns[1]
    g.build(a, "house", warrior.uid)
    assert warrior.leaving and len(g.staying(a)) == D.MAX_PAWNS
    assert p.pawns[-1].kind == "peasant"
    g._end_turn()
    assert warrior not in p.pawns and len(p.pawns) == D.MAX_PAWNS


def test_full_house_can_keep_all_pawns():
    g, a, p = full_house()
    uids = [x.uid for x in p.pawns]
    g.build(a, "house")
    assert [x.uid for x in p.pawns] == uids


# ---- computer players and events -----------------------------------------
def test_events_change_nothing_without_events():
    g = new_game(2)
    assert all(ai.event_value(g, 0, e) == 0 for e in g.envs)


def test_every_event_has_a_trainable_number():
    keys = {k for zone in D.ZONE_EVENTS.values() for k in zone}
    assert {f"ev_{k}" for k in keys} == set(ai.EVENT_WEIGHTS)


def test_computer_likes_a_rich_vein_and_fears_a_third_pawn_in_territory():
    g, env = zone_game("mine", "rich_iron_vein")
    assert ai.event_value(g, 0, env) > 0
    g, env = zone_game("forest", "territorial_animals")
    to_zone(g, 0, env, 2)
    assert ai.event_value(g, 0, env) < 0


def test_computer_values_being_first_only_while_it_can_be():
    g, env = zone_game("plains", "trade_route")
    assert ai.event_value(g, 0, env) > 0
    g.first_here[env.eid] = 1
    assert ai.event_value(g, 0, env) == 0


def test_each_game_loads_its_own_trained_player(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "TRAINED_FILE", str(tmp_path / "trained_ai.json"))
    assert ai.trained_path(8, 3, True).endswith("trained_ai_8_3p_events.json")
    assert ai.trained_path(8, 2).endswith("trained_ai_8_2p.json")
    (tmp_path / "trained_ai_8.json").write_text('{"weights": {"home_max": 7}}')
    assert ai.load_for(8, 3, True)["home_max"] == 7
    (tmp_path / "trained_ai_8_3p_events.json").write_text('{"weights": {"home_max": 9}}')
    assert ai.load_for(8, 3, True)["home_max"] == 9


def test_war_ram_stats():
    assert D.PAWNS["beast_tamer"]["cost"] == 9
    assert D.PAWNS["beast_tamer"]["combat"] == 1
    assert D.PAWNS["beast_tamer"]["vs_mob"] == 1


def ram_points(g, pid):
    return sum(x.won_vp for x in g.players[pid].pawns)


def test_war_ram_earns_a_vp_for_each_fight_won():
    g, e, a, b = duel()
    ram = g.players[a].pawns[0]
    ram.kind = "beast_tamer"
    before = g.victory_points(a)[1]
    for _ in range(2):
        contest_for(g, e, {a: (FIGHT, None), b: (FIGHT, None)})
        g._settle = lambda rolls, mob: next(r for r in rolls if r["pid"] == a)
        g._resolve_fight(e, [a, b], {a: 0, b: 0})
    assert ram.won_vp == 2
    assert g.victory_points(a)[1] == before + 2


def test_war_ram_earns_nothing_for_a_lost_fight():
    g, e, a, b = duel()
    g.players[a].pawns[0].kind = "beast_tamer"
    contest_for(g, e, {a: (FIGHT, None), b: (FIGHT, None)})
    g._settle = lambda rolls, mob: next(r for r in rolls if r["pid"] == b)
    g._resolve_fight(e, [a, b], {a: 0, b: 0})
    assert ram_points(g, a) == 0


def test_war_ram_earns_nothing_without_a_fight():
    g, e, a, b = duel()
    g.players[a].pawns[0].kind = "beast_tamer"
    e.mob = None
    contest_for(g, e, {a: (SPLIT, None), b: (SPLIT, None)})
    g._resolve_split(e, [a, b], {a: 0, b: 0})
    assert ram_points(g, a) == 0


def test_war_ram_earns_a_vp_when_allies_beat_a_mob():
    g, e, a, b = duel()
    g.players[a].pawns[0].kind = "beast_tamer"
    e.mob = ("Spiders", 1)
    contest_for(g, e, {a: (SPLIT, None), b: (SPLIT, None)})
    dice = iter([[1], [6], [6]])  # the mob rolls first, then each player
    g._roll = lambda n: next(dice)
    g._resolve_split(e, [a, b], {a: 0, b: 0})
    assert ram_points(g, a) == 1


def test_pawn_list_changes():
    assert "diplomat" not in D.PAWNS
    assert D.PAWNS["healer"]["combat"] == 1 and D.PAWNS["healer"]["cost"] == 7
    assert D.PAWNS["alchemist"]["cost"] == 7
    assert D.PAWNS["treasure_hunter"]["cost"] == 9 and "combat" not in D.PAWNS["treasure_hunter"]
    assert D.PAWNS["champion"]["combat"] == 4
    assert D.pawn_vp("treasure_hunter") == 2


def test_building_and_prize_changes():
    b = D.BUILDINGS
    assert b["alchemy_lab"]["vp"] == 10 and b["alchemy_lab"]["cost"]["iron"] == 2
    assert b["armory"]["vp"] == 11 and b["market_stall"]["vp"] == 7
    assert b["temple"]["vp"] == 23 and b["temple"]["cost"]["stone"] == 4
    assert ("iron", 2) in D.ENVIRONMENTS["mountain"]["prizes"]
    assert ("iron", 2) in D.ENVIRONMENTS["mine"]["prizes"]


def merchant_game(kind="merchant"):
    g = new_game(2)
    a = g.active
    p = g.players[a]
    p.pawns[0].kind = kind
    p.res.update({"wood": 9})
    g.send(a, p.pawns[0].uid, TOWN)
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.active != a:
        g.end_actions(g.active)
    return g, a


@pytest.mark.parametrize("sold,bonus", [(1, 1), (5, 5), (7, 7), (12, 12)])
def test_merchant_earns_per_resource_with_no_max(sold, bonus):
    g, a = merchant_game()
    assert g.sale_value(a, {"wood": sold}) == sold + bonus


def test_only_the_merchant_earns_the_sale_bonus():
    g, a = merchant_game("peasant")
    assert g.sale_value(a, {"wood": 3}) == 3


def lab_game():
    g = new_game(2)
    a = g.active
    p = g.players[a]
    p.buildings = ["farm", "herb_garden", "alchemy_lab"]
    p.res.update({"herbs": 3, "wood": 0})
    while g.phase == "deploy":
        g.done_placing(g.active)
    while g.active != a:
        g.end_actions(g.active)
    return g, a, p


def test_alchemy_lab_turns_one_herbs_a_turn_and_pawns_can_still_build():
    g, a, p = lab_game()
    free = len(g.free_home(a))
    g.use_lab(a, "wood")
    assert p.res["wood"] == 2 and p.res["herbs"] == 2 and len(g.free_home(a)) == free
    with pytest.raises(GameError):
        g.use_lab(a, "stone")


@pytest.mark.parametrize("target,made", [("wood", 2), ("stone", 2), ("food", 2), ("iron", 1)])
def test_alchemy_lab_makes_two_basics_or_one_iron(target, made):
    g, a, p = lab_game()
    before = p.res[target]
    g.use_lab(a, target)
    assert p.res[target] == before + made


def test_alchemy_lab_needs_a_pawn_at_home_and_only_makes_four_things():
    g, a, p = lab_game()
    with pytest.raises(GameError):
        g.use_lab(a, "amber")
    for pawn in g.pawns_at(a, HOME):
        pawn.location = TOWN
    assert not g.can_use_lab(a)


def test_player_must_press_end_even_with_nothing_left_to_do():
    g, a, p = lab_game()
    while g.free_home(a):
        g.free_home(a)[0].used = True
    g._next_actor()
    assert g.phase == "actions" and g.active == a
    g.end_actions(a)
    assert g.active != a or g.phase != "actions"


def test_player_with_nobody_home_or_in_town_is_skipped():
    g = new_game(2)
    first = g.active
    for pawn in g.players[first].pawns:
        pawn.resting = True
    while g.phase == "deploy":
        g.done_placing(g.active)
    assert g.active != first


def test_vp_history_has_every_turn_and_counts_gold():
    g = new_game(2, turns=8, is_ai=True)
    g.players[0].gold = 25
    g.vp_history[0][0] = g.victory_points(0)[4]
    assert g.vp_history[0][0] == (25 + g.leftover_value(g.players[0])) // D.GOLD_PER_VP
    run_ai_game(g)
    for row in g.final:
        line = g.vp_history[row["pid"]]
        assert len(line) == 9 and line[-1] == row["total"]


def test_alchemist_can_build_transform_and_use_the_lab_in_one_turn():
    g, a, p = lab_game()
    pawn = g.free_home(a)[0]
    pawn.kind = "alchemist"
    for other in g.free_home(a)[1:]:
        other.resting = True
    p.res.update({"amber": 1, "wood": 2})
    g.transmute(a, "crystal")
    g.use_lab(a, "stone")
    g.build(a, "lumber_camp" if "lumber_camp" not in p.buildings else "quarry")
    assert pawn.brewed and pawn.used and p.lab_used and p.res["crystal"] >= 1


def test_tree_and_vp_changes():
    b = D.BUILDINGS
    assert b["market_stall"]["vp"] == 7
    assert b["statue"]["tier"] == 3 and b["statue"]["requires"] == ["market_stall"]
    assert b["statue"]["cost"] == {"stone": 4, "iron": 3} and b["statue"]["vp"] == 13
    assert b["bank"]["tier"] == 4 and b["bank"]["requires"] == ["statue"]
    assert b["bank"]["cost"] == {"stone": 4, "iron": 2, "crystal": 1} and b["bank"]["vp"] == 14
    assert b["guild_hall"]["vp"] == 17 and b["trophy_hall"]["vp"] == 17
    assert "bank" in b["castle"]["requires_any"] and "statue" not in b["castle"]["requires_any"]


@pytest.mark.parametrize("gold,income", [(4, 0), (5, 1), (24, 4), (75, 15), (200, 15)])
def test_bank_gives_one_gold_per_five_up_to_fifteen(gold, income):
    g = new_game()
    p = g.players[0]
    p.buildings = ["bank"]
    p.gold = gold
    g._produce(p)
    assert p.gold == gold + income


@pytest.mark.parametrize("first", ["workshop", "caravan_post"])
def test_the_guild_hall_needs_the_workshop_or_the_caravan_post(first):
    g = Game([("A", False), ("B", False)], seed=1)
    assert g.needs_text(0, "guild_hall") == "Needs Caravan Post or Workshop"
    g.players[0].buildings.append(first)
    assert not g.missing_requirements(0, "guild_hall")


def test_guild_hall_allows_a_ninth_pawn():
    g = new_game()
    p = g.players[0]
    assert g.pawn_limit(0) == 8
    p.buildings = ["guild_hall"]
    assert g.pawn_limit(0) == 9
    while len(p.pawns) < 8:
        g.add_pawn(0, "peasant")
    assert not g.must_dismiss(0)
    g.add_pawn(0, "peasant")
    assert g.must_dismiss(0)


def test_buildings_pay_for_their_materials_and_a_pawn_turn():
    # A building must beat selling its materials and using the pawn elsewhere.
    pawn_turn = 3
    for name, info in D.BUILDINGS.items():
        sold = sum(D.top_price(r) * n for r, n in info["cost"].items())
        assert D.building_vp(name) * D.GOLD_PER_VP > sold + pawn_turn, name


def infirmary_loss():
    g, env = zone_game("swamp", "fog")
    p = g.players[0]
    p.buildings.append("infirmary")
    return g, env, p


def test_infirmary_heals_one_chosen_pawn_when_the_turn_ends():
    g, env, p = infirmary_loss()
    to_zone(g, 0, env, 2)
    pawns = g.pawns_at(0, env.eid)
    pawns[0].kind, pawns[1].kind = "peasant", "warrior"
    g.report = {"wounds": []}
    g.choices = []
    g.harvest_queue = []
    g._wound(0, env)
    assert all(x.wounded_next for x in pawns) and not g.choices
    g._after_choices()
    assert g.harvest_stage == "choice" and g.choices[0]["kind"] == "saved"
    assert {v for v, _ in g.choice_options()} == {x.uid for x in pawns}
    g.choose(0, pawns[1].uid)
    assert pawns[0].resting and not pawns[1].resting


def test_infirmary_heals_only_one_pawn_however_many_fights_were_lost():
    g, env, p = infirmary_loss()
    to_zone(g, 0, env, 2)
    pawns = g.pawns_at(0, env.eid)
    g.choices = []
    for pawn in pawns:
        pawn.wounded_next = True
    assert g._infirmary_visit() and len(g.choices) == 1
    g._next_choice()
    assert not g.choices and sum(x.wounded_next for x in pawns) == 1
    assert not g._infirmary_visit()


def test_no_infirmary_no_visit():
    g, env, p = infirmary_loss()
    p.buildings.remove("infirmary")
    to_zone(g, 0, env, 2)
    g.choices = []
    p.pawns[0].wounded_next = True
    assert not g._infirmary_visit()


def test_infirmary_still_stops_zone_event_wounds():
    g, env, p = infirmary_loss()
    to_zone(g, 0, env, 2)
    assert g.woundable(0, env.eid) == []


def test_a_new_alchemist_cannot_transform_this_turn():
    g, a, p = full_roster()
    g.recruits[a][1] = "alchemist"
    p.res["amber"] = 1
    g.recruit(a, 1, p.pawns[1].uid)
    assert not g.can_transmute(a)


def lab_with_only(g, a, p):
    """Every pawn away except what the test leaves at home."""
    for pawn in p.pawns:
        pawn.location = "forest"
    g.recruits[a] = ["peasant"]


def test_a_recruited_pawn_cannot_run_the_alchemy_lab_until_next_turn():
    g, a, p = lab_game()
    lab_with_only(g, a, p)
    new = g.add_pawn(a, "peasant")
    new.new = True
    assert not g.can_use_lab(a)
    new.new = False
    assert g.can_use_lab(a)


def test_the_houses_new_peasant_cannot_run_the_alchemy_lab():
    g, a, p = lab_game()
    builder = p.pawns[0]
    lab_with_only(g, a, p)
    builder.location = HOME
    p.res.update({"wood": 3, "stone": 2, "food": 2})
    g.build(a, "house")
    assert p.pawns[-1].new
    builder.location = "forest"
    assert not g.can_use_lab(a)


def test_a_wounded_pawn_cannot_run_the_alchemy_lab():
    g, a, p = lab_game()
    lab_with_only(g, a, p)
    wounded = p.pawns[0]
    wounded.location = HOME
    wounded.resting = True
    assert not g.can_use_lab(a)


def mason_game():
    g, a, p = lab_game()
    p.buildings = []
    p.pawns[0].kind = "mason"
    p.res.update({"wood": 10, "stone": 10, "food": 10})
    return g, a, p, p.pawns[0]


def test_a_mason_costs_nothing_extra_until_it_is_used():
    g, a, p, mason = mason_game()
    assert g.build_cost(a, "market_stall") == {"wood": 4, "food": 2}


def test_a_mason_halves_only_the_chosen_resource_until_a_building_is_built():
    g, a, p, mason = mason_game()
    g.use_mason(a, "wood")
    assert g.build_cost(a, "market_stall") == {"wood": 2, "food": 2}
    assert g.build_cost(a, "house") == {"wood": 2, "stone": 2, "food": 2}
    assert g.build_cost(a, "lumber_camp") == {"stone": 1, "food": 1}
    g.build(a, "farm")
    assert not p.halved and not g.half_price(a)
    assert g.build_cost(a, "market_stall") == {"wood": 4, "food": 2}


def test_another_pawn_builds_at_half_price_and_the_mason_stays_free():
    g, a, p, mason = mason_game()
    other = p.pawns[1]
    other.location = HOME
    g.use_mason(a, "wood")
    p.buildings.append("lumber_camp")
    wood = p.res["wood"]
    g.build(a, "market_stall")
    assert other.used and not mason.used and p.res["wood"] == wood - 2
    assert not g.can_use_mason(a) and g.free_home(a) == [mason]
    assert g.build_cost(a, "farm") == {"wood": 2}
    g.build(a, "farm")
    assert mason.used


def test_a_mason_that_already_built_can_still_give_its_discount():
    g, a, p, mason = mason_game()
    other = p.pawns[1]
    other.location = HOME
    other.used = True
    g.build(a, "farm")
    assert mason.used
    other.used = False
    assert g.can_use_mason(a)


@pytest.mark.parametrize("building,resource,cost", [
    ("farm", "wood", {"wood": 1}),
    ("lumber_camp", "stone", {"stone": 1, "food": 1}),
    ("quarry", "wood", {"wood": 1, "food": 1}),
    ("market_stall", "wood", {"wood": 2, "food": 2}),
    ("market_stall", "food", {"wood": 4, "food": 1}),
    ("house", "wood", {"wood": 2, "stone": 2, "food": 2}),
    ("house", "stone", {"wood": 3, "stone": 1, "food": 2}),
    ("house", "food", {"wood": 3, "stone": 2, "food": 1}),
])
def test_mason_prices(building, resource, cost):
    g, a, p, mason = mason_game()
    g.use_mason(a, resource)
    assert g.build_cost(a, building) == cost


def test_the_mason_choice_can_be_changed_before_building():
    g, a, p, mason = mason_game()
    g.use_mason(a, "wood")
    g.use_mason(a, "food")
    assert g.build_cost(a, "market_stall") == {"wood": 4, "food": 1}


def test_the_mason_cannot_halve_a_rare_resource():
    g, a, p, mason = mason_game()
    with pytest.raises(GameError):
        g.use_mason(a, "amber")


def test_a_mason_works_once_and_ends_with_the_turn():
    g, a, p, mason = mason_game()
    g.use_mason(a, "wood")
    g.build(a, "farm")
    assert not g.can_use_mason(a)
    p.halved = "stone"
    g._end_turn()
    g.start_turn()
    assert not p.halved and not p.halves_used


def test_a_new_or_wounded_mason_cannot_be_used():
    g, a, p, mason = mason_game()
    mason.new = True
    assert not g.can_use_mason(a)
    mason.new = False
    mason.resting = True
    assert not g.can_use_mason(a)


def loss_to(mob, advanced=True, pawns=1, gold=5):
    """A player loses a fight against this mob."""
    g, env = zone_game("swamp", "fog")
    g.advanced = g.mob_abilities = advanced
    p = g.players[0]
    p.gold = gold
    to_zone(g, 0, env, pawns)
    g.report = {"wounds": [], "awards": [], "text": ""}
    return g, env, p, {"name": mob, "count": 3, "strength": 3}


def test_goblins_take_gold_per_goblin_but_never_below_zero():
    g, env, p, mob = loss_to("Gnolls")
    g._beaten_by_mob(0, mob, env.eid)
    assert p.gold == 2
    g._beaten_by_mob(0, mob, env.eid)
    assert p.gold == 0


def test_mob_abilities_are_for_advanced_games_only():
    g, env, p, mob = loss_to("Gnolls", advanced=False)
    g._beaten_by_mob(0, mob, env.eid)
    assert p.gold == 5
    g._beat_mob(0, {"name": "Skeletons"})
    assert g.report["awards"] == []


@pytest.mark.parametrize("name,gift", [("Bears", "food"), ("Skeletons", "iron")])
def test_beaten_mobs_leave_a_resource(name, gift):
    g, env, p, _ = loss_to(name)
    g._beat_mob(0, {"name": name})
    assert g.report["awards"] == [(0, gift, 1)]


def test_mole_rats_wound_a_random_pawn_even_a_healer():
    g, env, p, mob = loss_to("Snakes")
    for pawn in p.pawns:
        pawn.kind = "healer"
    g._beaten_by_mob(0, mob, env.eid)
    assert sum(x.wounded_next for x in p.pawns) == 1


def test_the_infirmary_can_heal_a_mole_rat_wound():
    g, env, p, mob = loss_to("Snakes")
    p.buildings.append("infirmary")
    g._beaten_by_mob(0, mob, env.eid)
    g.choices = []
    assert sum(x.wounded_next for x in p.pawns) == 1
    g._infirmary_visit()
    g._next_choice()
    assert not any(x.wounded_next for x in p.pawns)


def test_the_workshop_works_like_a_mason():
    g, a, p, mason = mason_game()
    mason.kind = "peasant"
    assert not g.can_use_mason(a)
    p.buildings.append("workshop")
    g.use_mason(a, "wood")
    assert g.build_cost(a, "market_stall") == {"wood": 2, "food": 2}


def test_a_workshop_and_a_mason_give_two_discounts():
    g, a, p, mason = mason_game()
    p.buildings.append("workshop")
    p.pawns[1].location = HOME
    g.use_mason(a, "wood")
    g.build(a, "farm")
    assert g.can_use_mason(a)
    g.use_mason(a, "wood")
    g.build(a, "lumber_camp")
    assert not g.can_use_mason(a)


@pytest.mark.parametrize("count", [1, 4, 8])
def test_an_advanced_game_has_the_chosen_number_of_events(count):
    g = Game([(n, False) for n in "ABCD"], seed=count, events=count)
    assert g.advanced and len(g.events) == count


def test_a_basic_game_has_no_events_and_no_mob_abilities():
    g = Game([("A", False), ("B", False)], seed=1)
    assert not g.advanced and not g.events


def test_remaining_actions_lists_what_the_player_can_still_do():
    g, a, p = full_roster()
    p.res.update({"wood": 2, "food": 0})
    p.buildings = []
    p.gold = 6
    left = g.remaining_actions(a)
    assert any(x.startswith("Build:") and "Farm" in x for x in left)
    assert "Sell your resources" in left
    assert any(x.startswith("Recruit:") for x in left)


def test_nothing_left_means_no_question():
    g, a, p = full_roster()
    p.res = {r: 0 for r in p.res}
    p.gold = 0
    assert g.remaining_actions(a) == []


def test_the_alchemy_lab_is_listed_until_it_is_used():
    g, a, p = lab_game()
    assert "Use the Alchemy Lab" in g.remaining_actions(a)
    g.use_lab(a, "wood")
    assert "Use the Alchemy Lab" not in g.remaining_actions(a)


def test_the_goblin_alchemist_is_listed_when_it_can_transform():
    g, a, p = lab_game()
    p.buildings = []
    pawn = g.pawns_at(a, HOME)[0]
    pawn.kind = "alchemist"
    assert "Use the Goblin Alchemist" not in g.remaining_actions(a)
    p.res["amber"] = 1
    assert g.can_transmute(a) and "Use the Goblin Alchemist" in g.remaining_actions(a)


def test_a_mason_discount_counts_when_listing_buildings():
    g, a, p, mason = mason_game()
    p.res = {r: 0 for r in p.res}
    p.res.update({"wood": 2, "food": 2})
    assert "Market Stall" not in g.affordable_buildings(a)
    p.res["wood"] = 2
    p.res["food"] = 2
    p.buildings = ["farm", "lumber_camp"]
    assert "Market Stall" in g.affordable_buildings(a)
    assert not p.halved


def test_no_mob_is_called_horned_any_more():
    assert not any("Horned" in name for z in D.ENVIRONMENTS.values() for name, _ in z["mobs"])


def test_new_building_points():
    assert D.BUILDINGS["alchemy_lab"]["vp"] == 10 and D.BUILDINGS["infirmary"]["vp"] == 10


def test_can_pay_for_shows_what_is_affordable_even_with_no_free_pawn():
    g, a, p, mason = mason_game()
    p.res = {r: 0 for r in p.res}
    p.res.update({"wood": 2})
    assert g.can_pay_for(a, "farm")
    for pawn in p.pawns:
        pawn.location = "forest"
    assert g.can_pay_for(a, "farm") and not g.can_build(a, "farm")[0]
    assert not g.can_pay_for(a, "lumber_camp")
    p.buildings.append("farm")
    assert not g.can_pay_for(a, "farm")



# ---- factions -------------------------------------------------------------
def faction_game(faction="goblins", seed=1):
    g = Game([("A", False), ("B", False)], seed=seed, factions=[faction, "tidefolk"])
    return g, g.players[0]


@pytest.mark.parametrize("faction", list(D.FACTIONS))
def test_a_faction_replaces_the_two_peasants(faction):
    g, p = faction_game(faction)
    assert [x.kind for x in p.pawns] == D.FACTIONS[faction]["pawns"]
    assert g.victory_points(0)[1] == 3  # the strongest pawn 2 VP, the other 1 (the Raider 0)


def test_faction_pawns_are_never_offered_in_town():
    assert not set(D.FACTION_PAWNS) & set(D.RECRUIT_POOL)


def test_reef_hunter_collects_one_more_wood_or_food():
    for res in ("food", "wood"):
        g, p = faction_game("tidefolk")
        env = g.envs[0]
        env.harvest = [res]
        for pawn in p.pawns:
            pawn.location = env.eid
        g.report = {"gathers": [], "env": env.eid}
        before = p.res[res]
        g._gather(0, env)
        assert p.res[res] - before == 1 + 2


def test_stone_bull_collects_two_more_stone():
    g, p = faction_game("beasts")
    env = g.envs[0]
    env.harvest = ["stone"]
    for pawn in p.pawns:
        pawn.location = env.eid
    g.report = {"gathers": [], "env": env.eid}
    before = p.res["stone"]
    g._gather(0, env)
    assert p.res["stone"] - before == 1 + 3


def test_the_skull_shaman_swaps_two_basic_resources_per_turn():
    g, p = faction_game("goblins")
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    p.res.update({"wood": 2, "stone": 0})
    g.swap(0, "wood", "stone")
    g.swap(0, "wood", "stone")
    assert p.res["stone"] == 2 and p.res["wood"] == 0
    p.res["food"] = 1
    with pytest.raises(GameError):
        g.swap(0, "food", "stone")
    g3, q = faction_game("goblins")
    g3.phase = "actions"; g3.active = 0; g3.action_order = [0, 1]
    q.res["wood"] = 1
    with pytest.raises(GameError):
        g3.swap(0, "wood", "iron")


def test_raiders_collect_but_never_fight_for_the_prize():
    g, p = faction_game("goblins")
    env = g.envs[0]
    raider = next(x for x in p.pawns if x.kind == "raider")
    raider.location = env.eid
    assert g.fighters(0, env.eid) == []
    g.phase = "harvest"; g.harvest_queue = [env.eid]; g.harvest_stage = "next"
    before = p.res[env.harvest[0]]
    g.harvest_next()
    assert p.res[env.harvest[0]] == before + 1
    assert g.harvest_stage == "report" and "Raiders" in g.report["text"]


def test_the_dwarf_builder_takes_one_off_a_basic_resource():
    g, p = faction_game("dwarves")
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    p.buildings = ["farm", "lumber_camp"]
    g.use_trim(0, "wood")
    assert g.build_cost(0, "market_stall") == {"wood": 3, "food": 2}
    p.res.update({"wood": 3, "food": 2})
    g.build(0, "market_stall")
    assert not g.can_trim(0) and g.build_cost(0, "house")["wood"] == 3


def test_the_workshop_adds_to_the_dwarf_builder():
    g, p = faction_game("dwarves")
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    p.buildings = ["farm", "lumber_camp", "warehouse", "workshop"]  # the Workshop halves
    g.use_trim(0, "wood")
    g.use_mason(0, "stone")  # the Workshop adds to the Dwarf Builder's -1
    assert p.trimmed == "wood" and p.ws_halved == "stone" and not p.halved
    assert g.build_cost(0, "house") == {"wood": 2, "stone": 1, "food": 2}


def test_the_mason_and_the_dwarf_builder_never_add_up():
    g, p = faction_game("dwarves")
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    mason = g.add_pawn(0, "mason")
    mason.new = False
    g.use_trim(0, "wood")
    with pytest.raises(GameError):
        g.use_mason(0, "stone", "mason")  # the next building already has the Dwarf Builder's -1
    p.trimmed = ""
    g.use_mason(0, "stone", "mason")
    with pytest.raises(GameError):
        g.use_trim(0, "wood")  # the Mason already halves the next building
    assert p.halved == "stone" and not p.trimmed


def test_the_mason_and_the_workshop_add_up_on_two_resources():
    g, a, p, mason = mason_game()
    p.buildings += ["lumber_camp", "warehouse", "workshop"]
    g.use_mason(a, "wood", "mason")
    g.use_mason(a, "wood", "workshop")  # twice the same resource: 4 -> 2 -> 1
    assert g.build_cost(a, "market_stall") == {"wood": 1, "food": 2}
    g.use_mason(a, "food", "workshop")
    assert g.build_cost(a, "market_stall") == {"wood": 2, "food": 1}
    g.build(a, "market_stall")
    assert p.halves_used == 1 and p.ws_used and not p.halved and not p.ws_halved


def test_the_horn_blower_helps_one_neighbouring_zone():
    g, p = faction_game("dwarves")
    horn = next(x for x in p.pawns if x.kind == "horn_blower")
    builder = next(x for x in p.pawns if x.kind == "dwarf_builder")
    first = g.envs[0].eid
    near = g.neighbours(first)[0]
    far = next(e.eid for e in g.envs if e.eid != first and e.eid not in g.neighbours(first))
    horn.location, builder.location = first, near
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    assert g.horn_zones(0) == [near]
    before, own = g.strength(0, near, False), g.strength(0, first, False)
    g.set_horn(0, near)
    assert g.strength(0, near, False) == before + 1
    assert g.strength(0, first, False) == own - 1  # the Stone Slinger loses its own +1
    builder.location = far
    with pytest.raises(GameError):
        g.set_horn(0, far)


def test_town_is_not_a_neighbour():
    g, p = faction_game()
    assert all(TOWN not in g.neighbours(e.eid) for e in g.envs)


def test_panda_and_oar_shark_are_never_wounded():
    assert D.PAWNS["panda"]["tough"] and D.PAWNS["oar_shark"]["tough"] and D.PAWNS["panda"]["extra_die"]


def test_fight_bonuses_of_the_faction_pawns():
    assert D.PAWNS["oar_shark"]["combat"] == 2
    assert D.PAWNS["panda"]["combat"] == 1 and "combat" not in D.PAWNS["stone_bull"]


def test_the_spearman_can_build():
    g, p = faction_game("goblins")
    g.phase = "actions"; g.active = 0; g.action_order = [0, 1]
    for pawn in p.pawns:
        pawn.location = "forest"
    spear = next(x for x in p.pawns if x.kind == "spearman")
    spear.location = HOME
    p.res["wood"] = 5
    assert g.free_home(0) == [spear] and g.can_build(0, "farm")[0]


def test_a_player_with_every_pawn_out_still_gets_to_choose_the_horn_zone():
    g, p = faction_game("dwarves")
    horn = next(x for x in p.pawns if x.kind == "horn_blower")
    builder = next(x for x in p.pawns if x.kind == "dwarf_builder")
    first = g.envs[0].eid
    near = g.neighbours(first)[0]
    horn.location, builder.location = first, near
    for pawn in g.players[1].pawns:
        pawn.location = HOME
    g.phase = "actions"
    g.action_order = [0, 1]
    g._next_actor()
    assert g.active == 0 and g.can_horn(0)
    g.set_horn(0, near)
    g.end_actions(0)
    assert g.active == 1


def test_no_horn_target_means_no_extra_action_turn():
    g, p = faction_game("dwarves")
    for pawn in p.pawns:
        pawn.location = g.envs[0].eid
    for pawn in g.players[1].pawns:
        pawn.location = HOME
    g.phase = "actions"
    g.action_order = [0, 1]
    g._next_actor()
    assert g.active == 1


def test_snakes_wound_one_of_the_beaten_pawns_only():
    g, env, p, mob = loss_to("Snakes", pawns=2)
    home = [x for x in p.pawns if x.location == HOME]
    g._beaten_by_mob(0, mob, env.eid)
    assert sum(x.wounded_next for x in p.pawns) == 1
    assert not any(x.wounded_next for x in home)


def test_spiders_keep_a_beaten_pawn_in_the_zone_next_turn():
    g, env, p, mob = loss_to("Spiders", pawns=2)
    g._beaten_by_mob(0, mob, env.eid)
    caught = [x for x in p.pawns if x.web_next]
    assert len(caught) == 1 and caught[0].web_next == env.eid
    g.start_turn()
    pawn = caught[0]
    assert pawn.location == env.eid and pawn.placed and pawn.webbed and not pawn.resting
    assert pawn not in g.deployable(0)
    g.start_turn()
    assert pawn.location == HOME and not pawn.webbed


def test_a_wounded_pawn_in_a_web_rests_at_home():
    g, env, p, mob = loss_to("Spiders")
    g._beaten_by_mob(0, mob, env.eid)
    pawn = next(x for x in p.pawns if x.web_next)
    pawn.wounded_next = True
    g.start_turn()
    assert pawn.location == HOME and pawn.resting


def test_spiders_do_nothing_in_a_basic_game():
    g, env, p, mob = loss_to("Spiders", advanced=False)
    g._beaten_by_mob(0, mob, env.eid)
    assert not any(x.web_next for x in p.pawns)


def test_monster_abilities_can_be_switched_off_in_an_advanced_game():
    g = Game([("A", False), ("B", False)], seed=1, events=3, mob_abilities=False)
    assert g.advanced and not g.mob_abilities
    assert Game([("A", False), ("B", False)], seed=1, events=3).mob_abilities



def test_the_raider_never_fights_and_the_spearman_adds_nothing():
    g, p = faction_game("goblins")
    env = g.envs[0]
    for pawn in p.pawns:
        pawn.location = env.eid
    fighters = {x.kind for x in g.fighters(0, env.eid)}
    assert fighters == {"skull_shaman", "spearman"}
    assert g.strength_parts(0, env.eid, vs_mob=False)[0] == ("1 pawn", 1)  # only the Skull Shaman counts


def test_every_faction_has_a_difficulty_out_of_five():
    assert {k: f["difficulty"] for k, f in D.FACTIONS.items()} == {
        "beasts": 1, "tidefolk": 2, "goblins": 3, "dwarves": 3}
    levels = [f["difficulty"] for f in D.FACTIONS.values()]
    assert levels == sorted(levels)  # shown from the easiest to the hardest
    assert all(f["difficulty"] in D.DIFFICULTY_NAMES for f in D.FACTIONS.values())


def test_challenge_weak_gives_only_humans_minus_one_in_fights():
    g = Game([("A", False), ("B", True)], seed=2, challenge={"weak"})
    eid = g.envs[0].eid
    assert ("Challenge", -1) in g.strength_parts(0, eid, vs_mob=True)
    assert ("Challenge", -1) not in g.strength_parts(1, eid, vs_mob=True)  # the computer plays normally


def test_challenge_poor_makes_only_humans_start_with_nothing():
    g = Game([("A", False), ("B", True)], seed=2, challenge={"poor"})
    human, computer = g.players
    assert human.gold == 0 and not any(human.res.values())
    assert computer.gold == D.START_GOLD and computer.res["wood"] == D.START_RESOURCES["wood"]


def test_no_challenge_keeps_the_usual_start():
    g = Game([("A", False), ("B", True)], seed=2)
    assert g.players[0].gold == D.START_GOLD and ("Challenge", -1) not in g.strength_parts(0, g.envs[0].eid, False)


def test_the_thief_is_never_wounded():
    g = Game([("A", False), ("B", False)], seed=4)
    thief = g.add_pawn(0, "thief")
    thief.location = g.envs[0].eid
    assert D.PAWNS["thief"]["tough"] and thief not in g.woundable(0, g.envs[0].eid, fight=True)
