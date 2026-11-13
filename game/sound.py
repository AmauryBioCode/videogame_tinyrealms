"""Sound effects. The game is watched from frame to frame and each change it sees
(a new building, a pawn on the move, a fight...) plays a short sound from assets/sounds.
Sounds from RPG Essentials SFX by Leohpaz, the click from Kenney's UI Audio; the dice sound is made by code."""
import os

import pygame

import paths
from engine import HOME, TOWN, YIELD

# ---- which sound for what ---------------------------------------------------
FOLDER = os.path.join(paths.ROOT, "assets", "sounds")

VOLUME = {  # some sounds are recorded louder than others
    "click": 0.6, "recruit": 0.8, "heal": 0.45, "dice": 0.55, "step_rock": 0.4, "step_wood": 0.5,
}
# fight sounds play at full volume, and the music steps back while they play
FIGHT = {"punch", "slash", "fire", "poison", "arrow", "claw", "bite", "impact", "bones", "mob_death",
         "wound", "flee", "hit"}
# footsteps while a pawn walks (app.App.footsteps), by where it goes; home is grass too
STEPS = {HOME: "step_grass", "forest": "step_grass", "plains": "step_grass", "ruins": "step_grass", "mountain": "step_rock",
         "mine": "step_rock", "lake": "step_water", "swamp": "step_water", TOWN: "step_wood"}
# the most striking pawn in a fight decides its sound; any other pawn punches
ATTACKS = [("mage", "fire"), ("alchemist", "poison"), ("skull_shaman", "poison"), ("archer", "arrow"),
           ("panda", "claw"), ("beast_tamer", "claw"), ("oar_shark", "bite"), ("stone_bull", "impact"),
           ("champion", "slash"), ("knight", "slash"), ("warrior", "slash"), ("thief", "slash"),
           ("noble", "slash"), ("horn_blower", "slash")]
MOB_ATTACKS = {"Bears": "claw", "Gnolls": "impact", "Skeletons": "bones", "Snakes": "poison", "Spiders": "bite"}


def attack_sound(kinds):
    """The attack sound of a group of pawns, from its most striking kind."""
    for kind, name in ATTACKS:
        if kind in kinds:
            return name
    return "punch"


# ---- noticing changes in the game -------------------------------------------
def snapshot(game):
    """What the sounds compare from one frame to the next."""
    players = []
    for p in game.players:
        players.append({
            "res": dict(p.res), "gold": p.gold, "buildings": len(p.buildings),
            "pawns": {x.uid for x in p.pawns},
            "where": {x.uid: x.location for x in p.pawns if x.placed},
            "wounded": {x.uid for x in p.pawns if x.wounded_next},
            "resting": {x.uid for x in p.pawns if x.resting},
        })
    dice = tuple((e.eid, getattr(e, "event_die", None)) for e in game.envs)
    report = game.report
    zone = (game.turn, len(game.harvest_queue), report["env"]) if report else None
    fought = bool(report and (report.get("rolls") or report.get("mob")))
    return {"game": id(game), "players": players, "zone": zone, "fought": fought, "dice": dice}


def changes(before, after, game):
    """The sounds for what happened between two snapshots, as (name, delay in seconds)."""
    if not before or before["game"] != after["game"]:
        return []
    sounds = []
    for old, new in zip(before["players"], after["players"]):
        if new["buildings"] > old["buildings"]:
            sounds.append(("build", 0))
        if new["pawns"] - old["pawns"]:
            sounds.append(("recruit", 0.05))
        if new["gold"] > old["gold"]:
            sounds.append(("gold", 0))
        if any(new["res"][r] > old["res"].get(r, 0) for r in new["res"]):
            sounds.append(("resource", 0))
        healed = (old["wounded"] - new["wounded"]) & new["pawns"]
        if healed - new["resting"]:
            sounds.append(("heal", 0))
    new_zone = after["zone"] and after["zone"] != before["zone"]
    if new_zone and game.report.get("event_dice"):
        sounds.append(("dice", 0))
    if after["fought"] and (new_zone or not before["fought"]):  # the fight is rolled
        sounds += fight_sounds(game, game.report)
    if any(new != old and new[1] for old, new in zip(before["dice"], after["dice"])):
        sounds.append(("dice", 0))
    return sounds


def fight_sounds(game, report):
    """A zone's fight: each side's attack, then who fell or ran."""
    sounds = []
    rolls, mob = report.get("rolls", []), report.get("mob")
    delay = 0.15
    for roll in rolls:
        kinds = {x.kind for x in game.fighters(roll["pid"], report["env"])}
        sounds.append((attack_sound(kinds), delay))
        delay += 0.2
    if mob:
        sounds.append((MOB_ATTACKS.get(mob["name"], "impact"), delay))
        delay += 0.2
        if any(roll["score"] > mob["score"] for roll in rolls):
            sounds.append(("mob_death", delay + 0.3))
    if report.get("wounds"):
        sounds.append(("wound", delay + 0.35))
    if YIELD in report.get("stances", {}).values():
        sounds.append(("flee", 0.1))
    return sounds


# ---- playing sounds ---------------------------------------------------------
class Sounds:
    """Plays the effects, a little after they are asked for if they have a delay."""

    def __init__(self, folder=FOLDER, volume=0.7):
        """folder: where the .ogg files are. volume: the general volume of the effects."""
        self.folder = folder
        self.volume = volume
        self.muted = False
        self.cache = {}
        self.queue = []
        self.last = {}
        self.now = 0.0
        self.quiet_until = 0.0  # the music is lowered until then

    def music_level(self):
        """How loud the music may be now: lower while a fight is heard."""
        return 0.3 if self.now < self.quiet_until else 1.0

    def play(self, name, delay=0.0):
        """Ask for a sound, now or after a delay in seconds."""
        self.queue.append((self.now + delay, name))

    def update(self, dt):
        """Advance the clock and start the sounds that are due."""
        self.now += dt
        due = [item for item in self.queue if item[0] <= self.now]
        self.queue = [item for item in self.queue if item[0] > self.now]
        for _, name in due:
            if self.now - self.last.get(name, -1) < 0.09:
                continue  # the same sound many times at once would only be louder
            self.last[name] = self.now
            self._start(name)

    def _start(self, name):
        """Load (once) and play a sound. Fight sounds play loud and quiet the music."""
        if self.muted:
            return
        try:
            if not pygame.mixer.get_init():
                return
            if name not in self.cache:
                path = os.path.join(self.folder, f"{name}.ogg")
                self.cache[name] = pygame.mixer.Sound(path) if os.path.exists(path) else None
            sound = self.cache[name]
            if sound:
                if name in FIGHT:
                    sound.set_volume(1.0)
                    self.quiet_until = max(self.quiet_until, self.now + sound.get_length() + 0.6)
                else:
                    sound.set_volume(self.volume * VOLUME.get(name, 0.7))
                sound.play()
        except pygame.error:
            pass  # no sound card: play on in silence
