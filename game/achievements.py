"""Achievements: goals a human player can reach, kept from one game to the next.

Each achievement has a check that looks at the game (and at the counts the engine keeps in
player.stats). Some can be reached at any moment, others only once the game is over.
What has been unlocked is saved in a small file (or in the browser for the web version).
"""
import json
import os
import sys
import time

import data as D

# ---- the list ---------------------------------------------------------------
GROUPS = ["Buildings", "Pawns", "Mobs", "End of the game", "Factions", "AI"]


def _tier(p, n):
    return sum(D.BUILDINGS[b]["tier"] == n for b in p.buildings)


def _won(game, pid):
    """First place (a tie on VP and gold counts as a win), against at least one computer player."""
    if game.phase != "end" or not any(x.is_ai for x in game.players):
        return False
    top = game.final[0]
    return any(r["pid"] == pid and (r["total"], r["coins"]) == (top["total"], top["coins"]) for r in game.final)


def _advanced(game, x):
    """An Advanced AI looks ahead before each move; the Standard AI does not."""
    return x.is_ai and "lookahead" in (game.brains.get(x.pid) or {})


def _won_against(game, pid, advanced):
    """A win in a game with at least one Standard AI (advanced False) or one Advanced AI (advanced True)."""
    return _won(game, pid) and any(x.is_ai and _advanced(game, x) == advanced for x in game.players)


def _row(game, pid):
    return next(r for r in game.final if r["pid"] == pid)


def _staying(game, pid):
    return [x for x in game.players[pid].pawns if not x.leaving]


# (key, group, text, when, check). when: "any" = as soon as it happens, "end" = when the game is over.
ACHIEVEMENTS = [
    ("tier4", "Buildings", "Build a building of tier 4 in one game", "any", lambda g, p: _tier(p, 4) >= 1),
    ("bank15", "Buildings", "Make 15 gold in one turn with the Bank", "any",
     lambda g, p: p.stats.get("bank_best_turn", 0) >= 15),
    ("bank50", "Buildings", "Make 50 gold with the Bank in one game", "any", lambda g, p: p.stats.get("bank_gold", 0) >= 50),
    ("castle", "Buildings", "Build a Castle", "any", lambda g, p: "castle" in p.buildings),
    ("two_tier4", "Buildings", "Build two buildings of tier 4 in one game", "any", lambda g, p: _tier(p, 4) >= 2),
    ("fifteen", "Buildings", "Build 15 buildings in one game", "any", lambda g, p: len(p.buildings) >= 15),
    ("three_in_turn", "Buildings", "Build 3 buildings in the same turn", "any",
     lambda g, p: p.stats.get("most_built_in_a_turn", 0) >= 3),

    ("full", "Pawns", "Have the maximum of pawns at the end of the game", "end",
     lambda g, p: len(_staying(g, p.pid)) >= g.pawn_limit(p.pid)),
    ("black_knight", "Pawns", "Recruit a Black Knight", "any", lambda g, p: p.stats.get("recruited_champion", 0) >= 1),
    ("thief", "Pawns", "Steal 5 resources with the Thief in one game", "any", lambda g, p: p.stats.get("thief_steals", 0) >= 5),
    ("ram", "Pawns", "Win 5 VP with the War Ram in one game", "any", lambda g, p: p.stats.get("win_vp_beast_tamer", 0) >= 5),
    ("no_peasant", "Pawns", "Have no more Peasants at the end of the game (without a faction)", "end",
     lambda g, p: not p.faction and not any(x.kind == "peasant" for x in _staying(g, p.pid))),

    ("skeletons7", "Mobs", "Win a fight against Skeletons +7", "any", lambda g, p: p.stats.get("beat_Skeletons", 0) >= 7),

    ("pawn_vp20", "End of the game", "Make 20 VP or more with the pawns", "end",
     lambda g, p: dict(_row(g, p.pid)["lines"])["Pawns"] >= 20),
    ("gold50", "End of the game", "Have 50 gold or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["coins"] >= 50),
    ("gold100", "End of the game", "Have 100 gold or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["coins"] >= 100),
    ("vp100", "End of the game", "Have 100 VP or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["total"] >= 100),
    ("vp150", "End of the game", "Have 150 VP or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["total"] >= 150),
    ("vp180", "End of the game", "Have 180 VP or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["total"] >= 180),
    ("vp200", "End of the game", "Have 200 VP or more at the end of a game", "end", lambda g, p: _row(g, p.pid)["total"] >= 200),
] + [
    (f"win_{key}", "Factions", f"Win a game with the {D.FACTIONS[key]['name']} against one or more AI", "end",
     lambda g, p, key=key: p.faction == key and _won(g, p.pid))
    for key in D.FACTIONS
] + [
    ("win", "AI", "Win against one or more Standard AI", "end", lambda g, p: _won_against(g, p.pid, False)),
    ("win_advanced", "AI", "Win against one or more Advanced AI", "end", lambda g, p: _won_against(g, p.pid, True)),
    ("win_poor", "AI", "Win against one or more AI with no resources and gold at the beginning", "end",
     lambda g, p: "poor" in g.challenge and _won(g, p.pid)),
    ("win_weak", "AI", "Win against one or more AI with -1 in every fight", "end",
     lambda g, p: "weak" in g.challenge and _won(g, p.pid)),
    ("win_both", "AI", "Win against one or more AI with both challenges", "end",
     lambda g, p: {"poor", "weak"} <= set(g.challenge) and _won(g, p.pid)),
]
BY_KEY = {a[0]: a for a in ACHIEVEMENTS}


def reached(game, pid):
    """The achievements this player has reached in this game so far."""
    p = game.players[pid]
    over = game.phase == "end"
    return [key for key, _, _, when, check in ACHIEVEMENTS if (over or when == "any") and check(game, p)]


# ---- saving -----------------------------------------------------------------
WEB = sys.platform == "emscripten"
PATH = os.path.join(os.path.expanduser("~"), ".tiny_realms", "achievements.json")
WEB_KEY = "tiny_realms_achievements"


def load():
    """What has been unlocked: {key: {"name": who, "date": when}}."""
    try:
        if WEB:
            from platform import window  # the browser's page, in the web version
            text = window.localStorage.getItem(WEB_KEY)
        else:
            with open(PATH) as f:
                text = f.read()
        data = json.loads(text) if text else {}
        return {k: v for k, v in data.items() if k in BY_KEY}
    except Exception:
        return {}  # nothing saved yet, or the save can't be read


def save(unlocked):
    """Keep what has been unlocked for the next time the game is opened."""
    text = json.dumps(unlocked, indent=1)
    try:
        if WEB:
            from platform import window
            window.localStorage.setItem(WEB_KEY, text)
        else:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            with open(PATH, "w") as f:
                f.write(text)
    except Exception:
        pass  # can't save: the achievements still show for this session


class Tracker:
    """Watches the game for new achievements of the human players."""

    def __init__(self):
        self.unlocked = load()

    def update(self, game):
        """Check the game; returns the achievements just unlocked, as (key, player name)."""
        if game is None or getattr(game, "no_achievements", False):
            return []
        new = []
        for p in game.players:
            if p.is_ai:
                continue
            for key in reached(game, p.pid):
                if key not in self.unlocked:
                    self.unlocked[key] = {"name": p.name, "date": time.strftime("%Y-%m-%d")}
                    new.append((key, p.name))
        if new:
            save(self.unlocked)
        return new
