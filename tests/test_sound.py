"""The sound effects: which changes in the game play which sound."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))

import sound
from engine import TOWN, Game


def new_game():
    return Game([("A", False), ("B", False)], seed=3)


def names(before, game):
    return [name for name, _ in sound.changes(before, sound.snapshot(game), game)]


def test_every_sound_file_exists():
    wanted = {"click", "resource", "gold", "build", "recruit", "heal", "dice", "wound", "mob_death", "flee",
              "punch", *sound.STEPS.values(), *dict(sound.ATTACKS).values(), *sound.MOB_ATTACKS.values()}
    for name in wanted:
        assert os.path.exists(os.path.join(sound.FOLDER, f"{name}.ogg")), name


def test_gains_buildings_and_recruits_make_sounds():
    g = new_game()
    before = sound.snapshot(g)
    p = g.players[0]
    p.res["wood"] += 2
    p.gold += 3
    p.buildings.append("farm")
    g.add_pawn(0, "peasant")
    heard = names(before, g)
    assert {"resource", "gold", "build", "recruit"} <= set(heard)


def test_the_town_has_wooden_steps():
    assert sound.STEPS[TOWN] == "step_wood" and sound.STEPS["lake"] == "step_water"


def test_nothing_changed_is_silent():
    g = new_game()
    assert names(sound.snapshot(g), g) == []


def test_the_attack_sound_follows_the_most_striking_pawn():
    assert sound.attack_sound({"peasant"}) == "punch"
    assert sound.attack_sound({"peasant", "knight"}) == "slash"
    assert sound.attack_sound({"knight", "mage"}) == "fire"
    assert sound.attack_sound({"panda"}) == "claw"


def test_a_beaten_mob_dies_and_losers_are_hurt():
    g = new_game()
    report = {"env": g.envs[0].eid, "rolls": [{"pid": 0, "score": 9}], "wounds": [(1, "Peasant")],
              "mob": {"name": "Skeletons", "score": 7}, "stances": {}}
    heard = [name for name, _ in sound.fight_sounds(g, report)]
    assert heard == ["punch", "bones", "mob_death", "wound"]


def test_the_music_steps_back_during_a_fight():
    sounds = sound.Sounds()
    assert sounds.music_level() == 1.0
    sounds.quiet_until = 2.0
    assert sounds.music_level() < 1.0
    sounds.update(2.5)
    assert sounds.music_level() == 1.0


def test_an_event_die_rattles():
    g = new_game()
    before = sound.snapshot(g)
    g.envs[0].event_die = (5, True)
    assert names(before, g) == ["dice"]


def test_a_delayed_sound_waits_its_turn():
    played = []
    sounds = sound.Sounds()
    sounds._start = played.append
    sounds.play("build")
    sounds.play("gold", 0.5)
    sounds.update(0.1)
    assert played == ["build"]
    sounds.update(0.5)
    assert played == ["build", "gold"]
