"""Computer opponents.

Every choice is an estimate in gold, built from the numbers in DEFAULT_WEIGHTS.
train.py searches for better numbers and saves them in the trained_ai folder.
"""
import json
import os

import data as D
import paths
from engine import FIGHT, HOME, SPLIT, TOWN, YIELD

# ---- the numbers behind every choice (weights) ------------------------------
TRAINED_FILE = os.path.join(paths.ROOT, "trained_ai", "trained_ai.json")

DEFAULT_WEIGHTS = {
    # value of buildings, per turn left unless noted
    "produce": 0.8, "gold_income": 1.0, "end_value": 1.0, "peasant_build": 1.5, "interest": 1.5,
    "sale_bonus": 0.8, "combat_build": 1.0, "fight_build": 0.7, "gather": 1.5, "discount": 0.5,
    "amber": 1.5, "support": 0.5, "leftovers": 2.0, "tier": 0.0,
    # how buildings are compared
    "repeat": 0.75, "cost": 1.0, "unlock": 0.3, "build_min": 1.0, "keep_min": 4.0,
    # value of recruits
    "pawn_base": 2.0, "pawn_combat": 0.5, "pawn_worker": 0.8, "pawn_cost": 1.0, "recruit_min": 0.0,
    "upgrade_min": 2.0,  # with a full roster: how much better (in gold) a recruit must be to replace a pawn
    # value of environments
    "env_harvest": 1.0, "env_prize": 1.0, "env_share": 0.75, "env_second": 0.6, "mob_slope": 0.14,
    # where pawns go
    "home_max": 2.0, "town_stock": 5.0, "town_recruit": 3.0,
    # prize decisions
    "fight_margin": 2.0, "yield_margin": 3.0, "retreat": 0.2, "split_qty": 2.0,
}
# Zone events: how far to trust event_value's estimate for each one. 1.0 is as estimated.
EVENT_WEIGHTS = {f"ev_{key}": 1.0 for zone in D.ZONE_EVENTS.values() for key in zone}
DEFAULT_WEIGHTS.update(EVENT_WEIGHTS)
FIXED_WEIGHTS = {"variety": 1.0}  # random tastes, so plain computer towns look different


def load_trained(path=TRAINED_FILE):
    """Weights saved by train.py, or None if there are none yet."""
    try:
        with open(path) as f:
            saved = json.load(f)["weights"]
    except (OSError, ValueError, KeyError):
        return None
    return {**DEFAULT_WEIGHTS, **saved, "variety": 0.0}


def trained_path(turns, players=None, events=False):
    """Each game length, number of players and events setting has its own trained player."""
    name = f"trained_ai_{turns}"
    if players:
        name += f"_{players}p" + ("_events" if events else "")
    return os.path.join(os.path.dirname(TRAINED_FILE), name + ".json")


def load_for_turns(turns):
    """The player trained for this game length, or the general one."""
    return load_trained(trained_path(turns)) or load_trained()


def load_for(turns, players, events):
    """The player trained for exactly this game, or the closest one."""
    return load_trained(trained_path(turns, players, events)) or load_for_turns(turns)


def weights(game, pid):
    """The numbers this computer player decides with: its trained ones, or the plain defaults."""
    return game.brains.get(pid) or PLAIN


PLAIN = {**DEFAULT_WEIGHTS, **FIXED_WEIGHTS}


# ---- what things are worth --------------------------------------------------
def price_of(game, res):
    """Today's gold price of a resource (gold is worth 1)."""
    return 1 if res == "gold" else game.prices.get(res, D.RESOURCES[res][1])


def stock_value(game, pid):
    """What all of a player's resources would sell for today."""
    return sum(price_of(game, r) * n for r, n in game.players[pid].res.items())


# ---- choosing a building ----------------------------------------------------
def taste(game, pid, building, w):
    """Each plain computer player likes different buildings."""
    if not w.get("variety"):
        return 1.0
    tastes = game.__dict__.setdefault("ai_tastes", {})
    key = (pid, building)
    if key not in tastes:
        tastes[key] = game.rng.uniform(0.7, 1.6)
    return tastes[key]


def building_score(game, pid, building):
    """Estimated gold gained, minus the sale value of its materials."""
    w = weights(game, pid)
    info = D.BUILDINGS[building]
    p = game.players[pid]
    left = game.max_turns - game.turn
    value = D.building_vp(building) * D.GOLD_PER_VP * w["end_value"] + info["tier"] * w["tier"]
    value += info.get("gold_per_turn", 0) * left * w["gold_income"]
    value += sum(D.RESOURCES[r][1] * n * left * w["produce"] for r, n in info.get("produce", {}).items())
    if info.get("free_peasant"):
        value += min(left * w["peasant_build"], 10)
    if info.get("interest"):
        value += left * w["interest"] * max(1, min(D.INTEREST_MAX, p.gold // D.INTEREST_STEP)) / 3
    if info.get("sale_bonus"):
        value += left * w["sale_bonus"] * info["sale_bonus"]
    if info.get("combat"):
        value += left * w["combat_build"]
    if info.get("vs_mob") or info.get("extra_die") or info.get("vs_player"):
        value += left * w["fight_build"]
    if info.get("pawn_slots"):
        value += left * w["support"]
    if info.get("recruit_discount") or info.get("half_build") or info.get("town_bonus"):
        value += left * w["discount"]
    if info.get("herb_lab") and p.count("herb_garden"):
        value += left * w["amber"] * LAB_SHARE
    if info.get("no_wounds") or info.get("peasant_combat") or info.get("mob_prize"):
        value += left * w["support"]
    if info.get("full_leftovers"):
        value += w["leftovers"]
    value *= w["repeat"] ** p.count(building) * taste(game, pid, building, w)
    cost = sum(D.RESOURCES[r][1] * n for r, n in game.build_cost(pid, building).items())
    return value - cost * w["cost"]


CHILDREN = {b: [c for c in D.BUILDINGS if b in D.requirements(c)] for b in D.BUILDINGS}
TOP_DOWN = sorted(D.BUILDINGS, key=lambda b: -D.BUILDINGS[b]["tier"])


def plan_scores(game, pid):
    """Each building's score, plus some credit for what it unlocks in the tree."""
    w = weights(game, pid)
    p = game.players[pid]
    scores = {}
    for b in TOP_DOWN:
        score = building_score(game, pid, b)
        if p.count(b) == 0:
            score += sum(max(0, scores[c]) for c in CHILDREN[b]) * w["unlock"]
        scores[b] = score
    return scores


def best_building(game, pid):
    """The building worth building now, or None if nothing beats the minimum score."""
    w = weights(game, pid)
    best, score = None, w["build_min"]
    if not game.free_home(pid):
        return None, 0
    scores = plan_scores(game, pid)
    for b in D.BUILDINGS:
        if scores[b] > score and game.can_build(pid, b)[0]:
            best, score = b, scores[b]
    return best, score


# ---- choosing pawns and zones -----------------------------------------------
WIN_CHANCE = 0.3  # share of the remaining turns a fighter is expected to win
LAB_SHARE = 0.25  # what the Alchemy Lab is worth for a player trained with the old one


def pawn_score(game, pid, kind):
    """How much a recruit of this kind is worth to the player, in gold."""
    w = weights(game, pid)
    info = D.PAWNS[kind]
    left = game.max_turns - game.turn
    value = D.pawn_vp(kind) * D.GOLD_PER_VP + w["pawn_base"] * left
    value += (info.get("combat", 0) + info.get("vs_mob", 0)) * w["pawn_combat"] * left
    value += info.get("win_vp", 0) * D.GOLD_PER_VP * WIN_CHANCE * left
    if info.get("harvest") or info.get("idle_gold") or info.get("town_gold"):
        value += left * w["pawn_worker"]
    return value - info["cost"] * w["pawn_cost"]


def event_estimate(game, pid, env):
    """Rough gold value of this zone's event for one more pawn sent here now."""
    key = game.event_of(env.eid)
    res = env.harvest[0]
    mine = len(game.pawns_at(pid, env.eid))
    rivals = [len(game.pawns_at(o, env.eid)) for o in game.visitors_now(env.eid) if o != pid]
    first = env.eid not in game.first_here
    food, wood, stone, iron = (price_of(game, r) for r in ("food", "wood", "stone", "iron"))
    new = mine == 0  # most bonuses are per player, so only the first pawn earns them
    return {
        "wild_berries": food if new and res == "wood" else 0,
        "forest_fire": -0.8 if new else 0,
        "sacred_grove": wood if new else -wood if mine == 1 else 0,
        "territorial_animals": -3 if mine == 2 else 0,
        "high_ground": 1,
        "avalanche": -0.8 if new else 0,
        "crystal_caves": stone if new and res == "iron" else 0,
        "narrow_pass": -3 if mine >= 2 else 0,
        "mountain_shrine": 1,
        "good_fishing": food if new and res == "food" else 0,
        "abundance": 0.5,
        "golden_fish": 0.3 if new and res == "food" else 0,
        "deep_waters": 2 * food if mine == 1 and res == "food" else 0,
        "ancient_machinery": stone if new and res == "iron" else 0,
        "gold_nugget": 0.5 if new else 0,
        "rich_iron_vein": iron if new else 0,
        "rich_stone_vein": stone if new else 0,
        "prospectors_claim": iron if mine + 1 > max(rivals, default=0) >= mine else 0,
        "healing_mud": 1 if new else 0,
        "fog": -0.5,
        "sunken_treasure": 1,
        "swamp_gas": -0.5,
        "quicksand": 0.5,
        "plague": -0.8 if new else 0,
        "curse": -0.5,
        "trapped_relic": -0.5,
        "forgotten_treasury": 1,
        "ancient_knowledge": 1 if first else 0,
        "cursed_treasure": -1.5,
        "good_harvest": price_of(game, res) if new and res in ("food", "wood") else 0,
        "fertile_fields": (2 * food if new else -2 * food if mine == 1 else 0) if res == "food" else 0,
        "open_ground": -0.5,
        "trade_route": 1 if first else 0,
        "migrating_herds": 0.5,
        "friendly_monster": 2 + env.mob[1] if first and env.mob else 0,
    }.get(key, 0)


def event_value(game, pid, env):
    """What a zone's event is worth to the player, weighted by its training."""
    key = game.event_of(env.eid)
    return event_estimate(game, pid, env) * weights(game, pid)[f"ev_{key}"] if key else 0


def env_score(game, pid, env):
    """How good a zone is for the player's next pawn: resource, prize, mob, rivals and event."""
    w = weights(game, pid)
    harvest = sum(D.RESOURCES[r][1] for r in env.harvest) / len(env.harvest)
    res, qty = env.prize
    prize = price_of(game, res) * qty + price_of(game, "food") * env.extra_food
    rivals = [o for o in game.visitors_now(env.eid) if o != pid]
    chance = w["env_share"] / (1 + len(rivals))
    mob = game.known_mob(env)
    mine = 1 + game.strength(pid, env.eid, bool(mob))
    if mob:
        chance *= min(0.9, max(0.1, 0.5 + (mine - mob[1]) * w["mob_slope"]))
    already = w["env_second"] if game.pawns_at(pid, env.eid) else 1.0
    return harvest * w["env_harvest"] + prize * chance * already * w["env_prize"] + event_value(game, pid, env)


def is_quiet_and_full(game, pid, env):
    """Two pawns are enough where there is no mob and no other player."""
    alone = all(o == pid for o in game.visitors_now(env.eid))
    return not game.known_mob(env) and alone and len(game.pawns_at(pid, env.eid)) >= 2


def env_choices(game, pid):
    """A third pawn only goes to a quiet place if every place is taken up."""
    allowed = [e for e in game.envs if game.can_send(pid, e.eid)[0]]
    return [e for e in allowed if not is_quiet_and_full(game, pid, e)] or allowed


def best_recruit(game, pid):
    """The index of the best recruit worth its price, or None."""
    best, score = None, weights(game, pid)["recruit_min"]
    p = game.players[pid]
    for i, kind in enumerate(game.recruits[pid]):
        if kind and len(p.pawns) < game.pawn_limit(pid):
            s = pawn_score(game, pid, kind)
            if s > score:
                best, score = i, s
    return best, score


def pawn_value(game, pid, kind):
    """What a pawn of this kind is worth to the player once it is paid for, in gold."""
    return pawn_score(game, pid, kind) + D.PAWNS[kind]["cost"] * weights(game, pid)["pawn_cost"]


def upgrade_recruit(game, pid):
    """With a full roster: the best recruit worth replacing the weakest pawn, if the gold allows it.
    Returns (recruit index, uid of the pawn to send away), or (None, None)."""
    w = weights(game, pid)
    if not game.must_dismiss(pid) or not (game.free_town(pid) or game.caravan_recruit(pid)):
        return None, None
    pawns = game.dismissable(pid)
    if not pawns:
        return None, None
    worst = min(pawns, key=lambda x: (pawn_value(game, pid, x.kind), x.location == TOWN))
    best, gain = None, w["upgrade_min"]
    for i, kind in enumerate(game.recruits[pid]):
        if not kind or not game.can_recruit(pid, i)[0]:
            continue
        g = (pawn_value(game, pid, kind) - pawn_value(game, pid, worst.kind)
             - game.recruit_cost(pid, i) * w["pawn_cost"])
        if g > gain:
            best, gain = i, g
    return (best, worst.uid) if best is not None else (None, None)


def expected_recruit(game, pid):
    """The offers are hidden while placing: expect a good pawn out of the usual three
    (with a full roster, a good replacement for the weakest pawn)."""
    w = weights(game, pid)
    p = game.players[pid]
    if len([x for x in p.pawns if not x.leaving]) >= game.pawn_limit(pid):
        worst = min((pawn_value(game, pid, x.kind) for x in p.pawns if not x.leaving), default=0)
        gains = sorted(pawn_score(game, pid, kind) - worst for kind in D.RECRUIT_POOL)  # value - cost - worst
        return max(w["recruit_min"], gains[len(gains) * 3 // 4] - w["upgrade_min"])
    scores = sorted(pawn_score(game, pid, kind) for kind in D.RECRUIT_POOL)
    return max(w["recruit_min"], scores[len(scores) * 3 // 4])


def affordable_build_count(game, pid):
    """How many good buildings the current stock could pay for."""
    w = weights(game, pid)
    p = game.players[pid]
    stock = dict(p.res)
    count = 0
    scores = plan_scores(game, pid)
    for b in sorted(D.BUILDINGS, key=lambda b: -scores[b]):
        cost = D.BUILDINGS[b]["cost"]
        if (scores[b] > w["build_min"] and p.count(b) < D.BUILDINGS[b]["max"]
                and not game.missing_requirements(pid, b)
                and all(stock[r] >= n for r, n in cost.items())):
            for r, n in cost.items():
                stock[r] -= n
            count += 1
    return count


# ---- step 1: sending pawns --------------------------------------------------
def take_deploy(game):
    """Step 1: send one pawn (or keep it home), looking ahead first if that is turned on."""
    settings = weights(game, game.active).get("lookahead") or LOOKAHEAD
    if settings and not _simulating[0] and game.players[game.active].is_ai:
        move = lookahead_move(game, settings)
        if move:
            _apply_move(game, game.active, *move)
            return
    normal_deploy(game)


def normal_deploy(game):
    """Send one pawn (or keep it home) with the trained rules."""
    pid = game.active
    w = weights(game, pid)
    p = game.players[pid]
    pawns = game.deployable(pid)
    left = game.max_turns - game.turn
    placed_home = sum(1 for x in p.pawns if x.placed and x.location == HOME and not x.resting)
    in_town = len(game.pawns_at(pid, TOWN))

    town_pawns = [x for x in pawns if not x.info.get("no_town")]
    if left == 0 and in_town == 0 and town_pawns and any(p.res.values()):
        # last turn: someone must be in town to sell what is left once the building is done
        pawn = max(town_pawns, key=lambda x: x.info.get("sale_each", 0) * 2 + x.info.get("town_gold", 0))
        game.send(pid, pawn.uid, TOWN)
        return

    sent_out = sum(1 for x in p.pawns if x.location != HOME)
    if (placed_home < min(w["home_max"], affordable_build_count(game, pid))
            and (sent_out > 0 or len(pawns) > 1)):
        pawn = min(pawns, key=lambda x: (bool(x.info.get("no_build")), not x.info.get("half_build"),
                                         x.info.get("combat", 0)))
        if not pawn.info.get("no_build"):  # a pawn kept home to build must be able to build
            game.keep_home(pid, pawn.uid)
            return

    value = stock_value(game, pid)
    event = game.event_of(TOWN)
    if event == "market_tax":
        value -= 2 * w["ev_market_tax"]
    elif event == "traveling_merchant" and p.res["relic"] and not game.relic_sold:
        value += (12 - price_of(game, "relic")) * w["ev_traveling_merchant"]
    recruit = expected_recruit(game, pid)
    wants_town = (in_town == 0 and (value >= w["town_stock"]
                                    or (p.gold >= 4 and recruit > w["town_recruit"]) or left <= 1))
    if wants_town and value + p.gold > 0 and town_pawns:
        pawn = max(town_pawns, key=lambda x: x.info.get("sale_each", 0) * 2 + x.info.get("town_gold", 0))
        game.send(pid, pawn.uid, TOWN)
        return

    idle = [x for x in pawns if x.info.get("idle_gold") or x.info.get("alchemist")]
    if idle and len(pawns) == 1:
        game.keep_home(pid, idle[0].uid)
        return

    env = max(env_choices(game, pid), key=lambda e: env_score(game, pid, e))
    pawn = max(pawns, key=lambda x: x.info.get("combat", 0) + x.info.get("vs_mob", 0) * (1 if game.known_mob(env) else 0)
               - (x.info.get("no_bonus", False) or x.info.get("no_strength", False)) * 0.5)
    game.send(pid, pawn.uid, env.eid)


# ---- looking ahead before sending a pawn ---------------------------------------
# Before sending a pawn, the computer tries its options on copies of the game. On each copy, the rest
# of this turn and the next turn's building are played with the normal rules, with new dice, mobs and
# prices (the future is unknown). The option worth the most VP at the end wins, but only if it beats
# the normal choice by the margin: a lucky future must not change a good choice.
# Only the hard computer looks ahead: its brain has {"lookahead": {"futures": 4, "margin": 6, "zones": 3}}
# (see hard_brain). LOOKAHEAD, if set, turns it on for every computer (tests only).
LOOKAHEAD = None
_simulating = [False]


def _apply_move(game, pid, uid, destination):
    if destination == HOME:
        game.keep_home(pid, uid)
    else:
        game.send(pid, uid, destination)


def _play_until_next_harvest(g, stop_turn):
    """Play on with the normal rules until the next turn's building is over (or the game ends)."""
    while g.phase != "end" and not (g.turn > stop_turn or (g.turn == stop_turn and g.phase == "harvest")):
        if g.phase == "harvest" and g.harvest_stage == "next":
            g.harvest_next()
        elif g.phase == "harvest" and g.harvest_stage == "report":
            g.ack_report()
        elif not play_step(g):
            return


def _move_options(game, pid, zones, pairs="best"):
    """The moves the hard computer tries: keep a pawn home, send one to town, or to one of the best zones.
    With pairs="best", each place gets the pawn suited to it (the best seller in town, the strongest fighter
    in a zone, a builder at home), so only the place is chosen by looking ahead. With "all", every kind of
    pawn is tried everywhere."""
    pawns, seen = [], set()
    for x in game.deployable(pid):
        if (x.kind, x.won_vp) not in seen:
            seen.add((x.kind, x.won_vp))
            pawns.append(x)
    envs = sorted(env_choices(game, pid), key=lambda e: -env_score(game, pid, e))[:zones]
    if pairs == "all":
        moves = []
        for x in pawns:
            moves.append((x.uid, HOME))
            moves += [(x.uid, d) for d in [TOWN] + [e.eid for e in envs] if game.can_send(pid, d, x)[0]]
        return moves
    moves = []
    builders = [x for x in pawns if not x.info.get("no_build")]
    if builders:  # the weakest pawn able to build stays home
        home = min(builders, key=lambda x: (not x.info.get("half_build"), _fight_strength(game, x, None),
                                            game.pawn_points(x)))
        moves.append((home.uid, HOME))
    sellers = [x for x in pawns if game.can_send(pid, TOWN, x)[0]]
    if sellers:  # the best seller goes to town, the weakest fighter if they sell the same
        seller = max(sellers, key=lambda x: (x.info.get("sale_each", 0) * 2 + x.info.get("town_gold", 0),
                                             -_fight_strength(game, x, None)))
        moves.append((seller.uid, TOWN))
    for e in envs:  # the strongest fighter for that zone
        fighters = [x for x in pawns if game.can_send(pid, e.eid, x)[0]]
        if fighters:
            moves.append((max(fighters, key=lambda x: _fight_strength(game, x, e)).uid, e.eid))
    return moves


def lookahead_build(game, pid, normal, settings):
    """The hard computer's building: each building it can afford now (or none) is tried on a few possible
    futures, playing on until the next turn's building is over, and the one worth the most VP is built.
    The normal choice is kept unless another one is clearly better (the margin)."""
    import copy
    import random
    if not game.free_home(pid):
        return normal
    options = [b for b in D.BUILDINGS if game.can_build(pid, b)[0]]
    if not options:
        return normal
    if settings.get("tier_first"):  # the highest tier it can afford comes first
        top = max(D.BUILDINGS[b]["tier"] for b in options)
        if normal is None or D.BUILDINGS[normal]["tier"] < top:
            scores = plan_scores(game, pid)
            normal = max((b for b in options if D.BUILDINGS[b]["tier"] == top), key=lambda b: scores[b])
    if normal not in options:
        options.append(normal)  # normal may be None: not building now
    margin = settings.get("build_margin", settings["margin"])
    seeds = [random.randrange(10 ** 9) for _ in range(settings["futures"])]  # the same futures for every option
    _simulating[0] = True
    try:
        best, best_score = normal, None
        for option in options:
            total = 0
            for seed in seeds:
                g = copy.deepcopy(game)
                g.rng = random.Random(seed)
                g.log = lambda *a, **k: None
                if option:
                    g.build(pid, option)
                else:  # not building now: the home pawns stay idle this turn
                    for x in g.free_home(pid):
                        x.used = True
                _play_until_next_harvest(g, game.turn + settings.get("horizon", 1))
                total += g.victory_points(pid)[4]
            score = total / len(seeds) + (margin if option == normal else 0)
            if best_score is None or score > best_score:
                best, best_score = option, score
        return best
    finally:
        _simulating[0] = False


def _fight_strength(game, pawn, env):
    """How useful a pawn is in a fight in this zone (None: in general)."""
    info = pawn.info
    known = env is not None and game.known_mob(env)
    return (info.get("combat", 0) + info.get("vs_mob", 0) * (1 if known else 0)
            - (info.get("no_bonus", False) or info.get("no_strength", False)) * 0.5)


def lookahead_move(game, settings=None):
    """The move to make (pawn uid, destination), or None to keep the normal choice.
    settings: {"futures", "margin", "zones"}; by default the hard computer's, or LOOKAHEAD."""
    settings = settings or weights(game, game.active).get("lookahead") or LOOKAHEAD
    import copy
    import random
    pid = game.active
    _simulating[0] = True
    try:
        trial = copy.deepcopy(game)
        trial.log = lambda *a, **k: None
        waiting = {x.uid for x in trial.deployable(pid)}
        normal_deploy(trial)
        moved = [x for x in trial.players[pid].pawns if x.uid in waiting and x.placed]
        normal = (moved[0].uid, moved[0].location) if moved else None
        moves = _move_options(game, pid, settings["zones"], settings.get("pairs", "best"))
        if normal is None or len(moves) <= 1:
            return None
        if normal not in moves:
            moves.append(normal)
        seeds = [random.randrange(10 ** 9) for _ in range(settings["futures"])]  # the same futures for every move
        stop = game.turn + settings.get("horizon", 1)  # 1: until the next turn's building, 2: the one after
        best, best_score = None, None
        for move in moves:
            total = 0
            for seed in seeds:
                g = copy.deepcopy(game)
                g.rng = random.Random(seed)
                g.log = lambda *a, **k: None
                _apply_move(g, pid, *move)
                _play_until_next_harvest(g, stop)
                total += g.victory_points(pid)[4]
            score = total / len(seeds) + (settings["margin"] if move == normal else 0)
            if best_score is None or score > best_score:
                best, best_score = move, score
        return None if best == normal else best
    finally:
        _simulating[0] = False


ADVANCED_FILE = os.path.join(os.path.dirname(TRAINED_FILE), "advanced_ai.json")  # made by training/tune_advanced.py


def game_key(turns, players, events):
    """A name for one kind of game, for example 12_3p or 8_2p_events."""
    return f"{turns}_{players}p" + ("_events" if events else "")


def advanced_settings(turns, players, events):
    """The look-ahead settings tuned for this kind of game, or nothing if it isn't tuned yet."""
    try:
        with open(ADVANCED_FILE) as f:
            return json.load(f)[game_key(turns, players, events)]["settings"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def hard_brain(brain, futures=4, margin=6, zones=3, game_type=None):
    """The hard computer: the same trained numbers, plus looking ahead before each pawn.
    game_type (turns, players, events): use the settings tuned for that kind of game, if any."""
    settings = {"futures": futures, "margin": margin, "zones": zones}
    if game_type:
        settings.update(advanced_settings(*game_type))
    return {**(brain or PLAIN), "lookahead": settings}


# ---- step 2: building, recruiting and selling -------------------------------
def take_action(game):
    """Step 2: do one thing (swap, transform, build, recruit, sell, horn...) or end the turn."""
    pid = game.active
    left = game.max_turns - game.turn
    target = _alchemy_target(game, pid)
    if target:
        game.transmute(pid, target)
        return
    target = _lab_target(game, pid)
    if target:
        game.use_lab(pid, target)
        return
    if game.can_horn(pid) and not game.players[pid].horn:
        target = max(game.horn_zones(pid), key=lambda e: _horn_need(game, pid, e))
        own = next(x.location for x in game.players[pid].pawns if x.info.get("horn"))
        # helping costs the Stone Slinger its own +1, so only help a busier zone
        if _horn_need(game, pid, target) > _horn_need(game, pid, own):
            game.set_horn(pid, target)
            return
    swap = _shaman_swap(game, pid)
    if swap:
        game.swap(pid, *swap)
        return
    target = _mason_target(game, pid)
    if target:
        game.use_mason(pid, target)
    if game.can_trim(pid) and not game.players[pid].trimmed and not game.half_price(pid):  # discounts don't stack
        target = _wanted_cost(game, pid, D.BASIC_RESOURCES)
        if target:
            game.use_trim(pid, target)
    building, _ = best_building(game, pid)
    settings = weights(game, pid).get("lookahead")
    if settings and settings.get("build", True) and not _simulating[0] and game.players[pid].is_ai:
        building = lookahead_build(game, pid, building, settings)  # the hard computer compares the buildings
    if building:
        game.build(pid, building)
        return
    if game.free_sellers(pid) and not game.has_sold(pid):  # one well-chosen sale is enough
        lots = _lots_to_sell(game, pid, left)
        if lots and game.sale_value(pid, lots) > 0:
            game.sell(pid, lots)
            return
    if game.free_town(pid) or game.caravan_recruit(pid):
        index, _ = best_recruit(game, pid)
        if index is not None and game.can_recruit(pid, index)[0] and left > 1:
            game.recruit(pid, index)
            return
        index, dismiss = upgrade_recruit(game, pid)
        if index is not None:
            game.recruit(pid, index, dismiss)  # a better pawn replaces the weakest one
            return
        index, lots = forced_recruit(game, pid)
        if lots:
            game.sell(pid, lots)  # first the gold, then the recruit on the next move
            return
        if index is not None:
            game.recruit(pid, index)
            return
    game.end_actions(pid)


def next_building(game, pid):
    """The building this player is saving for: its best planned one it may build (affordable or not)."""
    p = game.players[pid]
    scores = plan_scores(game, pid)
    wanted = [b for b in D.BUILDINGS if p.count(b) < D.BUILDINGS[b]["max"] and not game.missing_requirements(pid, b)]
    return max(wanted, key=lambda b: scores[b], default=None)


def forced_recruit(game, pid):
    """Below the pawn limit, always recruit the best pawn that is not a Peasant, if the gold allows it,
    selling resources if needed, but never those the next building needs.
    Returns (recruit index, resources to sell first): (None, None) if no recruit is possible."""
    p = game.players[pid]
    if len([x for x in p.pawns if not x.leaving]) >= game.pawn_limit(pid):
        return None, None
    if not game.free_town(pid) and not game.caravan_recruit(pid):
        return None, None
    target = next_building(game, pid)
    keep = game.build_cost(pid, target) if target else {}
    spare = {r: n - keep.get(r, 0) for r, n in p.res.items() if n > keep.get(r, 0)}
    can_sell = bool(game.free_sellers(pid))
    money = p.gold + (game.sale_value(pid, spare) if can_sell and spare else 0)
    options = [i for i, kind in enumerate(game.recruits[pid])
               if kind and kind != "peasant" and game.recruit_cost(pid, i) <= money]
    if not options:
        return None, None
    index = max(options, key=lambda i: pawn_score(game, pid, game.recruits[pid][i]))
    if game.can_recruit(pid, index)[0]:
        return index, None
    # sell spare resources, the best-paid first, until the recruit is paid for
    lots, short = {}, game.recruit_cost(pid, index) - p.gold
    for r in sorted(spare, key=lambda r: -price_of(game, r)):
        for _ in range(spare[r]):
            if short <= 0:
                break
            lots[r] = lots.get(r, 0) + 1
            short = game.recruit_cost(pid, index) - p.gold - game.sale_value(pid, lots)
    return (index, lots) if short <= 0 and lots else (None, None)


def _horn_need(game, pid, eid):
    """Help where there are the most rivals and the strongest mob."""
    env = game.env(eid)
    rivals = sum(len(game.pawns_at(q.pid, eid)) for q in game.players if q.pid != pid)
    return rivals + (env.mob[1] if env.mob else 0)


def _wanted_cost(game, pid, allowed):
    """The resource the most wanted building is shortest of, among these."""
    w = weights(game, pid)
    p = game.players[pid]
    scores = plan_scores(game, pid)
    for b in sorted(D.BUILDINGS, key=lambda x: -scores[x]):
        if scores[b] <= w["build_min"] or p.count(b) >= D.BUILDINGS[b]["max"] or game.missing_requirements(pid, b):
            continue
        cost = {r: n for r, n in game.build_cost(pid, b).items() if r in allowed}
        return max(cost, key=lambda r: cost[r] - p.res[r]) if cost else None
    return None


def _shaman_swap(game, pid):
    """Swap a spare basic resource into one the wanted building lacks."""
    if not game.can_swap(pid):
        return None
    p = game.players[pid]
    need = _wanted_cost(game, pid, D.BASIC_RESOURCES)
    if not need:
        return None
    w = weights(game, pid)
    scores = plan_scores(game, pid)
    wanted = next((b for b in sorted(D.BUILDINGS, key=lambda x: -scores[x])
                   if scores[b] > w["build_min"] and p.count(b) < D.BUILDINGS[b]["max"]
                   and not game.missing_requirements(pid, b)), None)
    cost = game.build_cost(pid, wanted) if wanted else {}
    if p.res[need] >= cost.get(need, 0):
        return None
    spare = [r for r in D.BASIC_RESOURCES if r != need and p.res[r] > cost.get(r, 0)]
    return (max(spare, key=lambda r: p.res[r] - cost.get(r, 0)), need) if spare else None


def _mason_target(game, pid):
    """Halve what the most wanted building needs most."""
    if not game.can_use_mason(pid) or game.half_price(pid) or game.players[pid].trimmed:
        return None
    w = weights(game, pid)
    p = game.players[pid]
    scores = plan_scores(game, pid)
    for b in sorted(D.BUILDINGS, key=lambda x: -scores[x]):
        if scores[b] <= w["build_min"] or p.count(b) >= D.BUILDINGS[b]["max"] or game.missing_requirements(pid, b):
            continue
        cost = {r: n for r, n in D.BUILDINGS[b]["cost"].items() if r in D.MASON_RESOURCES and n > 1}
        return max(cost, key=lambda r: cost[r] - p.res[r]) if cost else None
    return None


def _lab_target(game, pid):
    """Turn Herbs into what the most wanted building is short of."""
    if not game.can_use_lab(pid):
        return None
    w = weights(game, pid)
    p = game.players[pid]
    scores = plan_scores(game, pid)
    for b in sorted(D.BUILDINGS, key=lambda x: -scores[x]):
        if (scores[b] <= w["keep_min"] or p.count(b) >= D.BUILDINGS[b]["max"]
                or game.missing_requirements(pid, b)):
            continue
        cost = D.BUILDINGS[b]["cost"]
        if p.res["herbs"] > cost.get("herbs", 0):
            for r in D.LAB_RESULTS:
                if cost.get(r, 0) > p.res[r]:
                    return r
        return None
    return None


def _alchemy_target(game, pid):
    """Make what a wanted building needs, or else whatever sells for more today."""
    if not game.can_transmute(pid):
        return None
    w = weights(game, pid)
    p = game.players[pid]
    scores = plan_scores(game, pid)
    for b in sorted(D.BUILDINGS, key=lambda x: -scores[x]):
        if (scores[b] <= w["keep_min"] or p.count(b) >= D.BUILDINGS[b]["max"]
                or game.missing_requirements(pid, b)):
            continue
        for r in D.ALCHEMY:
            if D.BUILDINGS[b]["cost"].get(r, 0) > p.res[r] and game.can_transmute(pid, r):
                return r
    gains = [r for r in D.ALCHEMY if game.can_transmute(pid, r)
             and game.prices[r] > game.prices[D.ALCHEMY[r]]]
    return max(gains, key=lambda r: game.prices[r] - game.prices[D.ALCHEMY[r]], default=None)


def _lots_to_sell(game, pid, left):
    """The resources to sell now: everything on the last turn (after building), otherwise what is not needed."""
    w = weights(game, pid)
    p = game.players[pid]
    if left == 0:
        return {r: n for r, n in p.res.items() if n}
    keep = {}
    scores = plan_scores(game, pid)
    for b in D.BUILDINGS:
        if (scores[b] > w["keep_min"] and p.count(b) < D.BUILDINGS[b]["max"]
                and not game.missing_requirements(pid, b)):
            for r, n in D.BUILDINGS[b]["cost"].items():
                keep[r] = max(keep.get(r, 0), n)
    return {r: n - keep.get(r, 0) for r, n in p.res.items() if n > keep.get(r, 0)}


# ---- step 3: choices and fights ---------------------------------------------
def choose_price(game):
    """Give up the least useful pawn, or the gold if that costs less."""
    options = game.choice_options()
    pawns = {x.uid: x for x in game.players[game.active].pawns}
    cost = lambda value: 3 if value == "pay" else 1 + game.pawn_points(pawns[value]) * 2
    if game.choices[0]["kind"] == "saved":
        return max(options, key=lambda option: cost(option[0]))[0]
    return min(options, key=lambda option: cost(option[0]))[0]


def choose_stance(game):
    """A stance the rules allow now: no split once someone chose to fight."""
    stance, target = _wanted_stance(game)
    allowed = [s for s, _, _ in game.stance_options(game.active)]
    if stance not in allowed:
        pid = game.active
        eid = game.contest["env"]
        mob = bool(game.env(eid).mob)
        mine = game.strength(pid, eid, mob)
        best = max(game.strength(o, eid, mob) for o in game.contest["players"] if o != pid)
        stance = FIGHT if mine + 1 >= best else YIELD
    return stance, None


def _wanted_stance(game):
    """The stance this player would like in the current fight, before checking it is allowed."""
    pid = game.active
    w = weights(game, pid)
    contest = game.contest
    eid = contest["env"]
    env = game.env(eid)
    _, qty = env.prize
    others = [o for o in contest["players"] if o != pid]
    mob = env.mob
    mine = game.strength(pid, eid, bool(mob))
    if game.turn == game.max_turns:
        return (FIGHT, None)  # the last turn: nothing to lose by fighting for the prize
    if not game.woundable(pid, eid, fight=True):
        return (FIGHT, None)  # pawns that can't be wounded risk nothing

    if not others:
        chance = (mine - mob[1] + 3.0) / 6
        return (FIGHT, None) if chance >= w["retreat"] else (YIELD, None)

    best_other = max(game.strength(o, eid, bool(mob)) for o in others)
    together = mine + sum(game.strength(o, eid, True) for o in others)
    if mob and mine + 3 <= mob[1] and together + 3 <= mob[1]:
        return (YIELD, None)
    if mine >= best_other + w["fight_margin"]:
        return (FIGHT, None)
    if mine <= best_other - w["yield_margin"] and not mob:
        return (YIELD, None)
    if mob and mine + 3 <= mob[1]:
        return (YIELD, None)  # a split means fighting the mob alone
    if qty >= w["split_qty"]:
        return (SPLIT, None)
    return (FIGHT, None)


# ---- one move for whoever's turn it is --------------------------------------
def play_step(game):
    """Make one decision for the active computer player. Returns False if none."""
    if game.phase == "deploy":
        take_deploy(game)
    elif game.phase == "actions":
        take_action(game)
    elif game.phase == "harvest" and game.harvest_stage == "stance":
        stance, target = choose_stance(game)
        game.set_stance(game.active, stance, target)
    elif game.phase == "harvest" and game.harvest_stage == "choice":
        game.choose(game.active, choose_price(game))
    else:
        return False
    return True
