"""Rules of the game, with no graphics, so they can be tested and simulated.

A turn:
  1. Dawn     buildings produce, environments and prices are revealed
  2. Deploy   players send pawns one at a time
  3. Actions  home pawns build, town pawns recruit or sell
  4. Harvest  pawns collect, then fight or negotiate for each bonus prize

Harvest comes after Actions, so resources collected this turn can never be
spent or sold during the same turn.
"""
import random
from dataclasses import dataclass, field

import data as D

HOME, TOWN = "home", "town"
FIGHT, SPLIT, YIELD = "fight", "split", "yield"


# ---- game pieces: pawns, players and zones ----------------------------------
@dataclass
class Pawn:
    """One pawn: its kind, owner, place on the board and what it has done this turn."""
    uid: int
    kind: str
    owner: int
    location: str = HOME
    placed: bool = False   # has received its order this turn
    used: bool = False     # has built or recruited this turn
    sold: bool = False     # has made its sale this turn
    resting: bool = False  # wounded: skips this turn
    wounded_next: bool = False
    stuck: bool = False       # left behind in a zone: skips this turn
    stuck_next: bool = False
    web_next: str = None      # caught by Spiders: starts next turn in this zone
    webbed: bool = False      # held in a web this turn
    arrival: int = 0          # placement order, for Narrow Pass
    won_vp: int = 0           # VP earned by winning fights
    brewed: bool = False      # the Alchemist has transformed this turn
    leaving: bool = False     # replaced by a new pawn: goes when this turn ends
    new: bool = False         # joined this turn: cannot run the Alchemy Lab yet

    @property
    def info(self):
        """The pawn's rules from data.PAWNS (cost, abilities...)."""
        return D.PAWNS[self.kind]

    @property
    def name(self):
        """The pawn's display name, such as Peasant."""
        return self.info["name"]


@dataclass
class Player:
    """One player: resources, gold, buildings, pawns and per-turn flags."""
    pid: int
    name: str
    color: tuple
    is_ai: bool = False
    team: str = "red"  # which character colors this player uses
    gold: int = D.START_GOLD
    res: dict = field(default_factory=dict)
    pawns: list = field(default_factory=list)
    buildings: list = field(default_factory=list)
    done_placing: bool = False
    caravan_used: bool = False
    lab_used: bool = False
    halved: str = ""          # the resource the Mason halves on the next building
    halves_used: int = 0      # Mason discounts spent this turn
    ws_halved: str = ""       # the resource the Workshop halves on the next building
    ws_used: bool = False     # the Workshop's discount is spent this turn
    faction: str = None
    trimmed: str = ""         # the resource the Dwarf Builder takes 1 off
    trim_used: bool = False
    shaman_left: int = 0      # Skull Shaman swaps left this turn
    shaman_turn: int = 0
    horn: str = None          # the zone the Stone Slinger helps this turn
    stats: dict = field(default_factory=dict)  # counts for the achievements (achievements.py)

    def count(self, building):
        """How many of this building the player owns."""
        return self.buildings.count(building)

    def building_sum(self, key):
        """Add up a numeric effect over all this player's buildings."""
        return sum(D.BUILDINGS[b].get(key, 0) for b in self.buildings)

    def has_effect(self, key):
        """True if any owned building has this effect key."""
        return any(D.BUILDINGS[b].get(key) for b in self.buildings)

    def note(self, key, amount=1, best=False):
        """Count something for the achievements: added up, or the best value kept."""
        old = self.stats.get(key, 0)
        self.stats[key] = max(old, amount) if best else old + amount


@dataclass
class EnvState:
    """One zone on the board this turn: what it gives, its prize and its mob."""
    eid: str
    harvest: list = field(default_factory=list)
    prize: tuple = None
    mob: tuple = None
    extra_food: int = 0   # event: Food added to the bonus prize
    friend: tuple = None  # event: (player id, monster name, strength)
    event_die: tuple = None  # event: (value, success) of this turn's die

    @property
    def name(self):
        """The zone's display name, such as Forest."""
        return D.ENVIRONMENTS[self.eid]["name"]


# ---- small helpers ----------------------------------------------------------
def res_name(res):
    """The display name of a resource, or 'gold'."""
    return "gold" if res == "gold" else D.RESOURCES[res][0]


class GameError(Exception):
    """An illegal move. The interface prevents these; tests check for them."""


# ---- the game ---------------------------------------------------------------
class Game:
    """The whole game: players, zones, turn phases and every rule. The window (app.py) and the computer players
    (ai.py) only call its methods."""
    def __init__(self, players, turns=12, seed=None, events=False, factions=None, mob_abilities=None,
                 challenge=()):
        """players: list of (name, is_ai). events: False for a basic game. True or a
        number makes an advanced game, with mob abilities and that many zone events.
        factions: one faction key per player, whose pawns replace the two Peasants.
        challenge: harder rules for the human players only, so the computers are harder to beat:
        "weak" (-1 in every fight), "poor" (no gold or resources at the start)."""
        if not 2 <= len(players) <= 4:
            raise GameError("The game needs 2 to 4 players")
        self.rng = random.Random(seed)
        self.max_turns = turns
        self.turn = 0
        self.phase = "dawn"
        self.first = 0
        self.active = 0
        self.next_uid = 1
        self.challenge = set(challenge)
        self.logs = []
        self.players = []
        for i, (name, is_ai) in enumerate(players):
            p = Player(i, name, D.PLAYER_COLORS[i][1], is_ai, D.PLAYER_COLORS[i][0].lower())
            p.res = {r: 0 for r in D.RESOURCE_IDS}
            if "poor" in challenge and not is_ai:  # challenge: humans start with nothing
                p.gold = 0
            else:
                p.res.update(D.START_RESOURCES)
            self.players.append(p)
            p.faction = factions[i] if factions else None
            for kind in D.FACTIONS[p.faction]["pawns"] if p.faction else ("peasant", "peasant"):
                self.add_pawn(i, kind)
        count = D.zone_count(len(self.players))
        self.envs = [EnvState(e) for e in self.rng.sample(list(D.ENVIRONMENTS), count)]
        self.recruits = {}  # what each player can still buy; hidden until step 3
        self.prices = {}
        self.harvest_queue = []
        self.harvest_stage = None   # "next", "stance", "report" or "choice"
        self.contest = None
        self.report = None
        self.final = None
        self.brains = {}  # player id -> weights for a trained computer player
        self.action_order = []
        self.events = {}       # zone -> event key, for the whole game
        self.first_here = {}   # zone -> first player to place there this turn
        self.arrivals = 0
        self.relic_sold = False
        self.choices = []      # decisions events ask of players after a report
        self.infirmary_done = False
        self.hero = None
        self.advanced = bool(events)
        self.mob_abilities = self.advanced if mob_abilities is None else mob_abilities
        if events:
            self._draw_events(None if events is True else events)
        self.vp_history = {p.pid: [self.victory_points(p.pid)[4]] for p in self.players}  # one per turn
        self.start_turn()

    # ---- zone events --------------------------------------------------------
    def _draw_events(self, count=None):
        """Advanced game: give random zones a random event for the whole game, at most one disaster."""
        zones = [e.eid for e in self.envs] + [TOWN]
        self.rng.shuffle(zones)
        disaster = False
        for zone in zones[:count]:
            options = [k for k in D.ZONE_EVENTS[zone]
                       if not (disaster and k in D.RARE_DISASTERS)]
            self.events[zone] = self.rng.choice(options)
            disaster = disaster or self.events[zone] in D.RARE_DISASTERS
        if self.events.get(TOWN) == "wandering_hero":
            self.hero = self.rng.choice(D.RECRUIT_POOL)
            for p in self.players:
                self.add_pawn(p.pid, self.hero)
            self.log(f"Wandering Hero: everyone receives a {D.PAWNS[self.hero]['name']}")

    def event_of(self, zone):
        """The event key of a zone or of the town, or None."""
        return self.events.get(zone)

    def event_text(self, zone):
        """(name, description) of a zone's event, or None."""
        key = self.events.get(zone)
        return D.ZONE_EVENTS[zone][key] if key else None

    def mob_hidden(self, env):
        """Fog event: the mob stays hidden while pawns are being sent."""
        return self.event_of(env.eid) == "fog" and self.phase == "deploy"

    def known_mob(self, env):
        """The mob that players can see, which Fog hides during placement."""
        return None if self.mob_hidden(env) else env.mob

    def prize_text(self, env):
        """The zone's bonus prize in words, such as '3 Wood + 1 Food'."""
        res, qty = env.prize
        extra = f" + {env.extra_food} Food" if env.extra_food else ""
        return f"{qty} {res_name(res)}{extra}"

    def fighters(self, pid, eid):
        """The pawns that count in a fight. Raiders never fight for the prize."""
        pawns = [x for x in self.pawns_at(pid, eid) if not x.info.get("no_bonus")]
        if self.event_of(eid) == "narrow_pass":
            return sorted(pawns, key=lambda x: x.arrival)[:2]
        return pawns

    def _note(self, text):
        """Add a line to the current harvest report."""
        self.report.setdefault("notes", []).append(text)

    def _event_die(self, pid, ok, value, result):
        """A die rolled for an event, shown in the zone's report."""
        name = self.event_text(self.report["env"])[0]
        self.report.setdefault("event_dice", []).append((pid, name, value, ok, result))
        who = f"{self.players[pid].name}: " if pid is not None else ""
        self.log(f"{who}{name} die rolls {value}: {result}")

    def _event_gain(self, pid, res, qty):
        """A zone event gives resources: add them and show them in the report."""
        name = self.event_text(self.report["env"])[0]
        self.add_res(pid, res, qty)
        self.report["gathers"].append((pid, res, qty, name))

    def _gather_events(self, pid, env, res, pawns):
        """Extra gains from a zone's event."""
        key = self.event_of(env.eid)
        count = len(pawns)
        die = lambda: self.rng.randint(1, 6)
        if key == "wild_berries" and res == "wood":
            self._event_gain(pid, "food", 1)
        elif key == "sacred_grove" and count == 1:
            self._event_gain(pid, "wood", 1)
        elif key == "good_fishing" and res == "food":
            self._event_gain(pid, "food", 1)
        elif key in ("crystal_caves", "ancient_machinery") and res == "iron":
            self._event_gain(pid, "stone", 1)
        elif key == "golden_fish" and res == "food":
            value = die()
            self._event_die(pid, value == 6, value, "+2 gold" if value == 6 else "nothing (needs a 6)")
            if value == 6:
                self._event_gain(pid, "gold", 2)
        elif key == "deep_waters" and res == "food" and count >= 2:
            self._event_gain(pid, "food", 2)
        elif key == "gold_nugget":
            value = die()
            self._event_die(pid, value == 6, value, "+3 gold" if value == 6 else "nothing (needs a 6)")
            if value == 6:
                self._event_gain(pid, "gold", 3)
        elif key == "rich_iron_vein":
            self._event_gain(pid, "iron", 1)
        elif key == "rich_stone_vein":
            self._event_gain(pid, "stone", 1)
        elif key == "prospectors_claim":
            rivals = [len(self.pawns_at(o, env.eid)) for o in self.visitors(env.eid) if o != pid]
            if count > max(rivals, default=0):
                self._event_gain(pid, "iron", 1)
        elif key == "good_harvest" and res in ("food", "wood"):
            self._event_gain(pid, res, 1)
        elif key == "fertile_fields" and res == "food" and count == 1:
            self._event_gain(pid, "food", 2)

    def _zone_dangers(self, env, present):
        """Events that strike everyone in a zone once it has been collected."""
        key = self.event_of(env.eid)
        value = self.rng.randint(1, 6) if key in D.RARE_DISASTERS else 0
        if value:
            self._event_die(None, value != 1, value, "everyone here has a pawn wounded!" if value == 1
                            else "nothing happens (only a 1 strikes)")
        if value == 1:
            name = self.event_text(env.eid)[0]
            self._note(f"{name}! Each player here has a pawn wounded.")
            for pid in present:
                self.choices.append({"pid": pid, "kind": "wound", "env": env.eid,
                                     "why": f"{name}: choose the pawn that comes back wounded"})
        if key == "territorial_animals":
            for pid in present:
                if len(self.pawns_at(pid, env.eid)) > 2:
                    self.choices.append({"pid": pid, "kind": "left", "env": env.eid,
                                         "why": "Territorial Animals: choose the pawn you leave behind"})

    # ---- choices made after a fight -----------------------------------------
    def woundable(self, pid, eid, fight=False):
        """Who can be wounded. The Infirmary stops zone events, and heals one pawn when the turn ends."""
        p = self.players[pid]
        pawns = self.pawns_at(pid, eid)
        if (self.event_of(eid) == "healing_mud" or (p.has_effect("no_wounds") and not fight)
                or any(x.info.get("healer") for x in pawns)):
            return []
        return [x for x in pawns if not x.info.get("tough") and not x.wounded_next
                and not (fight and x.info.get("no_bonus"))]

    def choice_options(self, choice=None):
        """A decision's options as (value, label). Same-kind pawns count as one."""
        c = choice or self.choices[0]
        pid, eid = c["pid"], c["env"]
        options = []
        if c["kind"] == "curse" and self.players[pid].gold >= 2:
            options.append(("pay", "Lose 2 gold"))
        if c["kind"] == "left":
            pawns = [x for x in self.pawns_at(pid, eid) if not x.wounded_next]
        elif c["kind"] == "saved":
            pawns = [x for x in self.players[pid].pawns if x.uid in c["uids"]]
        else:
            pawns = self.woundable(pid, eid)
        kinds = {}
        for pawn in pawns:
            kinds.setdefault(pawn.kind, pawn)
        verb = {"left": "Leave", "saved": "Save"}.get(c["kind"], "Wound")
        options += [(x.uid, f"{verb} {x.name}") for x in kinds.values()]
        return options

    def _apply_choice(self, c, value):
        """Carry out the answer to a choice (pay, lose a pawn, save a pawn...)."""
        p = self.players[c["pid"]]
        if value == "pay":
            p.gold -= 2
            self.log(f"{p.name} pays 2 gold to the Cursed Treasure")
            return
        pawn = next(x for x in p.pawns if x.uid == value)
        if c["kind"] == "left":
            pawn.stuck_next = True
            self.log(f"{p.name}'s {pawn.name} stays behind and misses next turn")
        elif c["kind"] == "saved":
            pawn.wounded_next = False
            self.log(f"{p.name}'s Infirmary saves a {pawn.name}")
        else:
            pawn.wounded_next = True
            self.log(f"{p.name}'s {pawn.name} comes back wounded")

    def _next_choice(self):
        """Settle what has only one answer. True if a player must decide."""
        while self.choices:
            options = self.choice_options()
            if len(options) > 1:
                self.active = self.choices[0]["pid"]
                self.harvest_stage = "choice"
                return True
            c = self.choices.pop(0)
            if options:
                self._apply_choice(c, options[0][0])
        return False

    def choose(self, pid, value):
        """A player answers the choice in front of them."""
        if self.harvest_stage != "choice" or pid != self.active:
            raise GameError("Not your choice")
        if value not in [v for v, _ in self.choice_options()]:
            raise GameError("Not a valid choice")
        self._apply_choice(self.choices.pop(0), value)
        self._after_choices()

    def _after_choices(self):
        """Once every choice is answered, go on with the harvest or end the turn."""
        if self._next_choice():
            return
        if self.harvest_queue:
            self.harvest_stage = "next"
        elif not (self._infirmary_visit() and self._next_choice()):
            self._end_turn()

    def _infirmary_visit(self):
        """When the turn ends, each Infirmary heals one wounded pawn, once. True if any is asked."""
        if self.infirmary_done:
            return False
        self.infirmary_done = True
        for p in self.players:
            pawns = [x for x in p.pawns if x.wounded_next and not x.leaving]
            if pawns and p.has_effect("no_wounds"):
                self.choices.append({"pid": p.pid, "kind": "saved", "env": None, "uids": [x.uid for x in pawns],
                                     "why": "choose the pawn that is not wounded"})
        return bool(self.choices)

    # ---- helpers ------------------------------------------------------------
    def log(self, text):
        """Add a line to the game's story, printed in the terminal."""
        self.logs.append(text)

    def add_pawn(self, pid, kind):
        """Give a player a new pawn of this kind and return it."""
        pawn = Pawn(self.next_uid, kind, pid)
        self.next_uid += 1
        self.players[pid].pawns.append(pawn)
        return pawn

    def order(self):
        """Player numbers in turn order, starting with this turn's first player."""
        n = len(self.players)
        return [(self.first + i) % n for i in range(n)]

    def env(self, eid):
        """The zone with this id."""
        return next(e for e in self.envs if e.eid == eid)

    def visitors_now(self, eid):
        """Players with a pawn already sent to this environment."""
        return [p.pid for p in self.players if self.pawns_at(p.pid, eid)]

    def pawns_at(self, pid, location):
        """A player's pawns at a place (home, town or a zone), except resting ones."""
        return [p for p in self.players[pid].pawns if p.location == location and not p.resting]

    def add_res(self, pid, res, qty):
        """Give a player resources, or gold."""
        if res == "gold":
            self.players[pid].gold += qty
        else:
            self.players[pid].res[res] += qty

    # ---- 1. dawn ------------------------------------------------------------
    def start_turn(self):
        """Dawn: buildings produce, zones are revealed, prices change, pawns heal."""
        self.turn += 1
        self.phase = "dawn"
        self.log(f"--- Turn {self.turn}/{self.max_turns} ---")
        self.infirmary_done = False
        for p in self.players:
            p.done_placing = False
            p.caravan_used = False
            p.lab_used = False
            p.halved = ""
            p.halves_used = 0
            p.ws_halved = ""
            p.ws_used = False
            p.trimmed = ""
            p.trim_used = False
            p.shaman_left = 0
            p.shaman_turn = 0
            p.horn = None
            for pawn in p.pawns:
                pawn.location = HOME
                pawn.placed = False
                pawn.used = False
                pawn.sold = False
                pawn.brewed = False
                pawn.new = False
                pawn.resting = pawn.wounded_next or pawn.stuck_next
                pawn.stuck = pawn.stuck_next
                pawn.webbed = bool(pawn.web_next) and not pawn.resting
                if pawn.webbed:  # still in the web: it plays this turn in that zone
                    pawn.location = pawn.web_next
                    pawn.placed = True
                    self.log(f"{p.name}'s {pawn.name} is still caught in the web in {self.env(pawn.web_next).name}")
                pawn.wounded_next = False
                pawn.stuck_next = False
                pawn.web_next = None
            self._produce(p)
        self.recruits = {p.pid: [] for p in self.players}
        self.prices = {}
        for r, (_, base, rare) in D.RESOURCES.items():
            self.prices[r] = self.rng.choice(D.PRICE_ODDS.get(r, [base]))
        if self.event_of(TOWN) == "holy_grail":
            self.prices["relic"] = 10
        self.reveal_all()
        self.phase = "deploy"
        self.active = self.first
        self._skip_finished_placers()

    def _produce(self, p):
        """Everything a player's buildings produce at dawn."""
        gained = {}
        for b in p.buildings:
            for r, n in D.BUILDINGS[b].get("produce", {}).items():
                gained[r] = gained.get(r, 0) + n
        for r, n in gained.items():
            p.res[r] += n
        income = p.building_sum("gold_per_turn")
        if p.has_effect("interest"):
            interest = min(D.INTEREST_MAX, p.gold // D.INTEREST_STEP)
            income += interest
            p.note("bank_gold", interest)
            p.note("bank_best_turn", interest, best=True)
        p.gold += income
        if gained or income:
            parts = [f"+{n} {res_name(r)}" for r, n in gained.items()]
            if income:
                parts.append(f"+{income} gold")
            self.log(f"{p.name} produces {', '.join(parts)}")

    def reveal_all(self):
        """New resources and prizes. Mobs on the table: at most turn - 1, and at
        most the limit for this number of players."""
        for e in self.envs:
            self._reveal(e)
        players = len(self.players)
        hunted = [e for e in self.envs if D.zone_mobs(e.eid, players) and self.rng.random() < D.MOB_CHANCE]
        self.rng.shuffle(hunted)
        limit = min(self.turn - 1, D.MAX_MOBS)
        for env in hunted[:max(0, limit)]:
            env.mob = self.rng.choice(D.zone_mobs(env.eid, players))
        self.first_here = {}
        for env in self.envs:
            key = self.event_of(env.eid)
            if key in ("abundance", "migrating_herds"):
                value = self.rng.randint(1, 6)
                need = 4 if key == "abundance" else 5
                env.event_die = (value, value >= need)
                env.extra_food = int(value >= need)
                self.log(f"{self.event_text(env.eid)[0]} die rolls {value} in {env.name}: "
                         + ("+1 Food in the bonus prize" if value >= need else "nothing"))

    def _reveal(self, env):
        """Draw what a zone gives this turn, its prize and its mob."""
        info = D.ENVIRONMENTS[env.eid]
        env.harvest = [self.rng.choice(info["harvest"])]
        res, qty = self.rng.choice(info["prizes"])
        env.mob = None
        env.prize = (res, qty)
        env.extra_food = 0
        env.event_die = None
        env.friend = None

    # ---- 2. deploy ----------------------------------------------------------
    def deployable(self, pid):
        """Pawns that still need an order this turn."""
        return [x for x in self.players[pid].pawns if not x.placed and not x.resting]

    def _skip_finished_placers(self):
        """Move the turn on past players with no pawn left to send."""
        for i in range(len(self.players)):
            pid = (self.active + i) % len(self.players)
            p = self.players[pid]
            if not p.done_placing and self.deployable(pid):
                self.active = pid
                return
        self._start_actions()

    def _advance_deploy(self):
        """Next player's turn to send a pawn."""
        self.active = (self.active + 1) % len(self.players)
        self._skip_finished_placers()

    def _order_pawn(self, pid, uid):
        """Check that this pawn can get an order now, and return it."""
        if self.phase != "deploy" or pid != self.active:
            raise GameError("Not your turn to place")
        for pawn in self.deployable(pid):
            if pawn.uid == uid:
                return pawn
        raise GameError("This pawn cannot be sent")

    def send(self, pid, uid, destination):
        """Send one pawn to the town or to an environment."""
        pawn = self._order_pawn(pid, uid)
        if destination != TOWN and destination not in [e.eid for e in self.envs]:
            raise GameError("Unknown destination")
        allowed, reason = self.can_send(pid, destination, pawn)
        if not allowed:
            raise GameError(reason)
        pawn.location = destination
        pawn.placed = True
        self.arrivals += 1
        pawn.arrival = self.arrivals
        place = "Town" if destination == TOWN else self.env(destination).name
        self.log(f"{self.players[pid].name}: {pawn.name} goes to {place}")
        if destination != TOWN and destination not in self.first_here:
            self.first_here[destination] = pid
            self._first_arrival(pid, self.env(destination))
        self._advance_deploy()

    def can_send(self, pid, destination, pawn=None):
        """Can a pawn go there? Returns (allowed, reason)."""
        if destination == TOWN and pawn is not None and pawn.info.get("no_town"):
            return False, f"The {pawn.name} can't go to town"
        if destination == TOWN and self.pawns_at(pid, TOWN):
            return False, "Only one pawn per player in town"
        if self.event_of(destination) == "quicksand" and len(self.pawns_at(pid, destination)) >= 2:
            return False, "Quicksand: at most 2 pawns per player"
        return True, ""

    def _first_arrival(self, pid, env):
        """Events that happen to the first pawn a player sends to a zone."""
        key = self.event_of(env.eid)
        p = self.players[pid]
        if key == "trade_route":
            p.gold += 1
            self.log(f"Trade Route: {p.name} gains 1 gold")
        elif key == "friendly_monster" and env.mob:
            env.friend = (pid, env.mob[0], env.mob[1])
            env.mob = None
            self.log(f"Friendly Monster: {env.friend[1]} join {p.name} this turn")

    def keep_home(self, pid, uid):
        """Use your placement to keep one pawn at home."""
        pawn = self._order_pawn(pid, uid)
        pawn.placed = True
        self.log(f"{self.players[pid].name}: {pawn.name} stays home")
        self._advance_deploy()

    def done_placing(self, pid):
        """Every pawn not sent yet stays home."""
        if self.phase != "deploy" or pid != self.active:
            raise GameError("Not your turn to place")
        p = self.players[pid]
        p.done_placing = True
        staying = self.deployable(pid)
        for pawn in staying:
            pawn.placed = True
        if staying:
            names = ", ".join(x.name for x in staying)
            self.log(f"{p.name}: {names} {'stays' if len(staying) == 1 else 'stay'} home")
        else:
            self.log(f"{p.name} is done placing")
        self._advance_deploy()

    # ---- 3. actions ---------------------------------------------------------
    def _start_actions(self):
        """Step 2 starts: draw the recruits on offer and choose who acts first."""
        self.phase = "actions"
        offers = ["peasant"] + self.rng.sample(D.RECRUIT_POOL, D.RECRUITS_PER_TURN)
        self.recruits = {p.pid: list(offers) for p in self.players}  # buying only uses up your own copy
        self.action_order = self.order()
        self._next_actor()

    def _next_actor(self):
        """The next player who has something to do in step 2, or move on to the harvest."""
        while self.action_order:
            pid = self.action_order[0]
            if self.pawns_at(pid, HOME) or self.pawns_at(pid, TOWN) or self.horn_zones(pid):
                self.active = pid  # stays until the player presses End
                return
            self.action_order.pop(0)
            self._end_of_actions(pid)
        self._start_harvest()

    def free_home(self, pid):
        """Pawns at home that can still build this turn. Some faction pawns never build."""
        return [x for x in self.pawns_at(pid, HOME) if not x.used and not x.info.get("no_build")]

    def free_sellers(self, pid):
        """Town pawns can sell as many times as they like."""
        return self.pawns_at(pid, TOWN)

    def has_sold(self, pid):
        """True if the player already sold this turn."""
        return any(x.sold for x in self.pawns_at(pid, TOWN))

    # ---- special pawns: alchemists, lab and mason ---------------------------
    def free_town(self, pid):
        """Pawns in town that have not recruited yet."""
        return [x for x in self.pawns_at(pid, TOWN) if not x.used]

    def free_alchemists(self, pid):
        """Alchemists at home that can still transform a resource."""
        return [x for x in self.pawns_at(pid, HOME) if x.info.get("alchemist") and not x.brewed]

    def can_transmute(self, pid, target=None):
        """Is a free Alchemist able to make this, or anything if no target is given?"""
        p = self.players[pid]
        targets = [target] if target else list(D.ALCHEMY)
        return bool(self.free_alchemists(pid)) and any(
            t in D.ALCHEMY and p.res[D.ALCHEMY[t]] >= 1 for t in targets)

    def transmute(self, pid, target):
        """A free Goblin Alchemist turns Amber into Crystal or Pearl into Gemme."""
        self._check_action(pid)
        if target not in D.ALCHEMY:
            raise GameError("The Alchemist only makes Crystal or Gemme")
        if not self.can_transmute(pid, target):
            raise GameError(f"Needs a free Alchemist and 1 {res_name(D.ALCHEMY[target])}")
        p = self.players[pid]
        pawn = self.free_alchemists(pid)[0]
        p.res[D.ALCHEMY[target]] -= 1
        p.res[target] += 1
        pawn.brewed = True
        self.log(f"{p.name}'s {pawn.name} makes 1 {res_name(target)}")

    def can_use_lab(self, pid, target=None):
        """Can a pawn at home use the Alchemy Lab this turn?"""
        p = self.players[pid]
        return (p.has_effect("herb_lab") and not p.lab_used and p.res["herbs"] >= 1
                and bool(self.lab_pawns(pid)) and (target is None or target in D.LAB_RESULTS))

    def lab_pawns(self, pid):
        """Pawns at home that can run the Alchemy Lab: not wounded and not new this turn."""
        return [x for x in self.pawns_at(pid, HOME) if not x.new]

    def use_lab(self, pid, target):
        """Turn 1 Herbs into 2 Wood, 2 Stone, 2 Food or 1 Iron. Pawns can still build."""
        self._check_action(pid)
        if target not in D.LAB_RESULTS:
            raise GameError("The Alchemy Lab only makes Wood, Stone, Food or Iron")
        if not self.can_use_lab(pid, target):
            raise GameError("Needs the Alchemy Lab, a free pawn at home and 1 Herbs")
        p = self.players[pid]
        p.res["herbs"] -= 1
        made = D.LAB_RESULTS[target]
        p.res[target] += made
        p.lab_used = True
        self.log(f"{p.name}'s Alchemy Lab makes {made} {res_name(target)}")

    def _check_action(self, pid):
        """Raise an error unless it is this player's turn in step 2."""
        if self.phase != "actions" or pid != self.active:
            raise GameError("Not your turn to act")

    def half_price(self, pid):
        """A resource the Mason or the Workshop is halving on the next building, if any."""
        p = self.players[pid]
        return p.halved or p.ws_halved

    def masons_left(self, pid):
        """Each Mason at home (not wounded, not new) gives one discount per turn."""
        p = self.players[pid]
        return sum(1 for x in self.pawns_at(pid, HOME) if x.info.get("half_build") and not x.new) - p.halves_used

    def halves_left(self, pid):
        """Discounts left this turn: one per Mason at home, plus one for the Workshop."""
        p = self.players[pid]
        return self.masons_left(pid) + (1 if p.has_effect("half_build") and not p.ws_used else 0)

    def can_halve(self, pid, source):
        """source "mason" or "workshop": that discount is left this turn, with a free pawn at home to build.
        The Workshop adds to the Mason or the Dwarf Builder, but the Mason and the Dwarf Builder don't
        add to each other."""
        p = self.players[pid]
        if self.phase != "actions" or not self.free_home(pid):
            return False
        if source == "workshop":
            return p.has_effect("half_build") and not p.ws_used
        return self.masons_left(pid) > 0 and not p.trimmed

    def can_use_mason(self, pid):
        """A Mason or Workshop discount can still be put on the next building."""
        p = self.players[pid]
        return ((self.can_halve(pid, "mason") and not p.halved)
                or (self.can_halve(pid, "workshop") and not p.ws_halved))

    def use_mason(self, pid, resource, source=None):
        """The next building costs half of this resource, whichever pawn builds it.
        source: "mason" or "workshop"; by default the first one still free."""
        self._check_action(pid)
        p = self.players[pid]
        if resource not in D.MASON_RESOURCES:
            raise GameError("The Mason can't halve that resource")
        if source is None:
            if self.can_halve(pid, "mason") and not p.halved:
                source = "mason"
            elif self.can_halve(pid, "workshop") and not p.ws_halved:
                source = "workshop"
            else:  # both set or only one there: change that choice
                source = "mason" if self.can_halve(pid, "mason") else "workshop"
        if not self.can_halve(pid, source):
            if source == "mason" and p.trimmed:
                raise GameError("The Dwarf Builder already lowers the next building")
            raise GameError("Needs a Mason at home" if source == "mason" else "Needs a Workshop")
        if source == "mason":
            p.halved = resource
        else:
            p.ws_halved = resource
        who = "Mason" if source == "mason" else "Workshop"
        self.log(f"{p.name}'s {who} will halve {res_name(resource)} on the next building")

    # ---- building -----------------------------------------------------------
    def _pick_builder(self, pid):
        """The pawn at home that builds, keeping the most useful ones free."""
        pawns = self.free_home(pid)
        pawns.sort(key=lambda x: (bool(x.info.get("half_build")), bool(x.info.get("idle_gold"))))
        return pawns[0] if pawns else None

    def build_cost(self, pid, building):
        """Cost after the Mason or Workshop discount."""
        cost = dict(D.BUILDINGS[building]["cost"])
        p = self.players[pid]
        for half in (p.halved, p.ws_halved):  # the same resource can be halved twice, rounded up each time
            if half in cost:
                cost[half] = (cost[half] + 1) // 2
        if p.trimmed in cost and sum(cost.values()) > 1:
            cost[p.trimmed] -= 1
            if not cost[p.trimmed]:
                del cost[p.trimmed]
        return cost

    def missing_requirements(self, pid, building):
        """Buildings still needed before this one can be built."""
        owned = self.players[pid].buildings
        info = D.BUILDINGS[building]
        missing = [b for b in info.get("requires", []) if b not in owned]
        options = info.get("requires_any", [])
        if options and not any(b in owned for b in options):
            missing += options
        return missing

    def needs_text(self, pid, building):
        """Plain words for what must be built first, or an empty string."""
        missing = self.missing_requirements(pid, building)
        if not missing:
            return ""
        word = " or " if D.BUILDINGS[building].get("requires_any") else " and "
        return "Needs " + word.join(D.BUILDINGS[b]["name"] for b in missing)

    def can_pay_for(self, pid, building):
        """Unlocked, not at its limit, and the resources are there. A free pawn is not needed."""
        p = self.players[pid]
        return (p.count(building) < D.BUILDINGS[building]["max"] and not self.missing_requirements(pid, building)
                and all(p.res[r] >= n for r, n in self.build_cost(pid, building).items()))

    def can_build(self, pid, building):
        """Return (allowed, reason)."""
        p = self.players[pid]
        if not self.free_home(pid):
            return False, "No free pawn at home"
        if p.count(building) >= D.BUILDINGS[building]["max"]:
            return False, "Limit reached"
        needs = self.needs_text(pid, building)
        if needs:
            return False, needs
        if len(p.buildings) >= D.MAX_BUILDINGS:
            return False, "No building plots left"
        for r, n in self.build_cost(pid, building).items():
            if p.res[r] < n:
                return False, "Not enough resources"
        return True, ""

    def build(self, pid, building, dismiss=None):
        """dismiss: with a full roster, a pawn to replace with the free Peasant."""
        self._check_action(pid)
        allowed, reason = self.can_build(pid, building)
        if not allowed:
            raise GameError(reason)
        p = self.players[pid]
        cost = self.build_cost(pid, building)
        for r, n in cost.items():
            p.res[r] -= n
        self._pick_builder(pid).used = True
        if p.halved:
            p.halved = ""
            p.halves_used += 1
        if p.ws_halved:
            p.ws_halved = ""
            p.ws_used = True
        if p.trimmed:
            p.trimmed = ""
            p.trim_used = True
        p.buildings.append(building)
        p.note(f"built_turn_{self.turn}")
        p.note("most_built_in_a_turn", p.stats[f"built_turn_{self.turn}"], best=True)
        self.log(f"{p.name} builds a {D.BUILDINGS[building]['name']}")
        leaving = next((x for x in self.dismissable(pid) if x.uid == dismiss), None)
        if leaving and D.BUILDINGS[building].get("free_peasant") and self.must_dismiss(pid):
            self._replace(p, leaving)
        if D.BUILDINGS[building].get("free_peasant") and not self.must_dismiss(pid):
            pawn = self.add_pawn(pid, "peasant")
            pawn.used = True
            pawn.placed = True
            pawn.new = True
        self._next_actor()

    # ---- recruiting ---------------------------------------------------------
    def _use_town_pawn(self, pid, key, flag, pawns):
        """Each town pawn recruits once (sales are unlimited). The Caravan Post
        gives one extra recruit per turn."""
        p = self.players[pid]
        pawns = sorted(pawns, key=lambda x: -x.info.get(key, 0))
        if flag == "used" and p.has_effect("town_bonus") and not p.caravan_used:
            p.caravan_used = True
            return
        setattr(pawns[0], flag, True)

    def recruit_cost(self, pid, index):
        """The gold price of recruit number index, after discounts."""
        p = self.players[pid]
        cost = D.PAWNS[self.recruits[pid][index]]["cost"] - p.building_sum("recruit_discount")
        town = self.free_town(pid)
        if town:
            cost -= max(x.info.get("recruit_discount", 0) for x in town)
        return max(1, cost)

    def can_recruit(self, pid, index):
        """Can the player recruit this pawn now? Returns (allowed, reason)."""
        p = self.players[pid]
        if not self.free_town(pid) and not self.caravan_recruit(pid):
            return False, "No free pawn in town"
        if self.recruits[pid][index] is None:
            return False, "Already recruited"
        if p.gold < self.recruit_cost(pid, index):
            return False, "Not enough gold"
        return True, ""

    def caravan_recruit(self, pid):
        """The Caravan Post's extra recruit, once a town pawn has recruited."""
        p = self.players[pid]
        return bool(self.pawns_at(pid, TOWN)) and p.has_effect("town_bonus") and not p.caravan_used

    def pawn_limit(self, pid):
        """How many pawns this player may have (8, or 9 with a Guild Hall)."""
        return D.MAX_PAWNS + self.players[pid].building_sum("pawn_slots")

    def must_dismiss(self, pid):
        """With a full roster, a new recruit replaces one of your pawns."""
        return len(self.staying(pid)) >= self.pawn_limit(pid)

    def staying(self, pid):
        """Pawns that are not replaced at the end of this turn."""
        return [x for x in self.players[pid].pawns if not x.leaving]

    def dismissable(self, pid):
        """Any pawn, even the one recruiting in town: it plays this turn, then leaves."""
        return self.staying(pid)

    def _replace(self, player, pawn):
        """The pawn still plays this turn, and leaves before the next one."""
        pawn.leaving = True
        self.log(f"{player.name} will replace a {pawn.name} next turn")

    def recruit(self, pid, index, dismiss=None):
        """dismiss: the uid of the pawn to send away, when the roster is full."""
        self._check_action(pid)
        allowed, reason = self.can_recruit(pid, index)
        if not allowed:
            raise GameError(reason)
        p = self.players[pid]
        leaving = None
        if self.must_dismiss(pid):
            leaving = next((x for x in self.dismissable(pid) if x.uid == dismiss), None)
            if not leaving:
                raise GameError("Choose a pawn to dismiss first")
        p.gold -= self.recruit_cost(pid, index)
        self._use_town_pawn(pid, "recruit_discount", "used", self.free_town(pid))
        kind = self.recruits[pid][index]
        self.recruits[pid][index] = None
        if leaving:
            self._replace(p, leaving)
        pawn = self.add_pawn(pid, kind)
        p.note(f"recruited_{kind}")
        pawn.used = True
        pawn.placed = True
        pawn.brewed = True  # a new Alchemist starts working next turn
        pawn.new = True
        self.log(f"{p.name} recruits a {pawn.name}")
        self._next_actor()

    # ---- selling ------------------------------------------------------------
    def sale_value(self, pid, lots):
        """The gold a sale of these resources would bring today."""
        p = self.players[pid]
        total = sum(self.prices[r] * n for r, n in lots.items())
        town = self.free_sellers(pid)
        if total and town:
            total += sum(lots.values()) * max(x.info.get("sale_each", 0) for x in town)
        total += p.building_sum("sale_bonus") if total else 0
        if self.event_of(TOWN) == "traveling_merchant" and lots.get("relic") and not self.relic_sold:
            total += 12 - self.prices["relic"]
        if self.event_of(TOWN) == "market_tax":
            total = max(0, total - 2)
        return total

    def sell(self, pid, lots):
        """Sell any amount of the resources you hold, as often as you like."""
        self._check_action(pid)
        p = self.players[pid]
        lots = {r: n for r, n in lots.items() if n > 0}
        if not self.free_sellers(pid):
            raise GameError("No free pawn in town")
        if not lots or any(p.res[r] < n for r, n in lots.items()):
            raise GameError("Nothing valid to sell")
        value = self.sale_value(pid, lots)
        self.relic_sold = self.relic_sold or lots.get("relic", 0) > 0
        for r, n in lots.items():
            p.res[r] -= n
        p.gold += value
        self.free_sellers(pid)[0].sold = True
        self.log(f"{p.name} sells {sum(lots.values())} resources for {value} gold")
        self._next_actor()

    # ---- what is left to do -------------------------------------------------
    def affordable_buildings(self, pid):
        """What this player can build now, counting the Mason, Workshop and Dwarf Builder discounts."""
        p = self.players[pid]
        saved = p.halved, p.ws_halved, p.trimmed
        masons = [p.halved] + (list(D.MASON_RESOURCES) if self.can_halve(pid, "mason") and not p.halved else [])
        shops = [p.ws_halved] + (list(D.MASON_RESOURCES) if self.can_halve(pid, "workshop") and not p.ws_halved else [])
        trims = [p.trimmed] + (list(D.BASIC_RESOURCES) if self.can_trim(pid) and not p.trimmed else [])
        combos = [(m, w, t) for m in masons for w in shops for t in trims
                  if not (m and t)]  # the Mason and the Dwarf Builder don't add up
        names = []
        for b in D.BUILDINGS:
            if any(self._try_cost(pid, b, *c) for c in combos):
                names.append(D.BUILDINGS[b]["name"])
        p.halved, p.ws_halved, p.trimmed = saved
        return names

    def _try_cost(self, pid, building, halved, ws_halved, trimmed):
        """Could the building be paid with these discount choices?"""
        p = self.players[pid]
        p.halved, p.ws_halved, p.trimmed = halved, ws_halved, trimmed
        return self.can_build(pid, building)[0]

    def remaining_actions(self, pid):
        """What the player can still do before ending the turn."""
        p = self.players[pid]
        left = []
        buildings = self.affordable_buildings(pid)
        if buildings:
            shown = ", ".join(buildings[:4]) + (f" and {len(buildings) - 4} more" if len(buildings) > 4 else "")
            left.append(f"Build: {shown}")
        if self.free_sellers(pid) and any(p.res.values()) and not self.has_sold(pid):
            left.append("Sell your resources")
        offers = [D.PAWNS[kind]["name"] for i, kind in enumerate(self.recruits[pid])
                  if kind and self.can_recruit(pid, i)[0]]
        if offers:
            left.append("Recruit: " + ", ".join(offers))
        if self.can_transmute(pid):
            left.append("Use the Goblin Alchemist")
        if self.can_use_lab(pid):
            left.append("Use the Alchemy Lab")
        if self.can_swap(pid):
            left.append("Use the Skull Shaman")
        if self.can_horn(pid) and not self.players[pid].horn:
            left.append("Choose the Stone Slinger's zone")
        return left

    # ---- faction abilities --------------------------------------------------
    def can_trim(self, pid):
        """A Dwarf Builder at home (not wounded), once per turn, with a free pawn to build."""
        p = self.players[pid]
        return (self.phase == "actions" and not p.trim_used and bool(self.free_home(pid))
                and any(x.info.get("trim_build") for x in self.pawns_at(pid, HOME)))

    def use_trim(self, pid, resource):
        """The next building costs 1 less of this resource."""
        self._check_action(pid)
        if resource not in D.BASIC_RESOURCES:
            raise GameError("The Dwarf Builder works with Wood, Stone or Food")
        if not self.can_trim(pid):
            raise GameError("Needs a Dwarf Builder at home")
        if self.players[pid].halved:
            raise GameError("The Mason already halves the next building")  # the Mason and the Dwarf don't add up
        self.players[pid].trimmed = resource
        self.log(f"{self.players[pid].name}'s next building costs 1 less {res_name(resource)}")

    def shaman_swaps_left(self, pid):
        """How many resources the Skull Shaman can still swap this turn."""
        p = self.players[pid]
        if self.phase != "actions" or not any(x.info.get("shaman") for x in self.pawns_at(pid, HOME)):
            return 0
        if p.shaman_turn != self.turn:
            return max(x.info.get("shaman", 0) for x in self.pawns_at(pid, HOME))
        return p.shaman_left

    def can_swap(self, pid, give=None, take=None):
        """Can the Skull Shaman swap give for take now?"""
        p = self.players[pid]
        if not self.shaman_swaps_left(pid):
            return False
        if give is None:
            return any(p.res[r] for r in D.BASIC_RESOURCES)
        return give in D.BASIC_RESOURCES and take in D.BASIC_RESOURCES and give != take and p.res[give] >= 1

    def swap(self, pid, give, take):
        """The Skull Shaman turns 1 basic resource into another, twice per turn."""
        self._check_action(pid)
        if not self.can_swap(pid, give, take):
            raise GameError("The Skull Shaman can't do that")
        p = self.players[pid]
        left = self.shaman_swaps_left(pid)
        p.shaman_turn = self.turn
        p.shaman_left = left - 1
        p.res[give] -= 1
        p.res[take] += 1
        self.log(f"{p.name}'s Skull Shaman turns 1 {res_name(give)} into 1 {res_name(take)}")

    def zone_spot(self, eid):
        """The (column, row) of a zone on the board."""
        return D.BOARD_SPOTS[[e.eid for e in self.envs].index(eid)]

    def neighbours(self, eid):
        """Zones that touch this one on the board, up, down, left or right."""
        x, y = self.zone_spot(eid)
        return [e.eid for e in self.envs if abs(self.zone_spot(e.eid)[0] - x) + abs(self.zone_spot(e.eid)[1] - y) == 1]

    def horn_zones(self, pid, check_target=True):
        """Zones the Stone Slinger can help: next to its own, with your pawns in them."""
        horns = [x for x in self.players[pid].pawns
                 if x.info.get("horn") and x.location not in (HOME, TOWN) and not x.resting]
        zones = []
        for horn in horns:
            for eid in self.neighbours(horn.location):
                if self.pawns_at(pid, eid) and eid not in zones:
                    zones.append(eid)
        return zones

    def can_horn(self, pid):
        """Can the player use the Stone Slinger now?"""
        return self.phase == "actions" and bool(self.horn_zones(pid))

    def set_horn(self, pid, eid):
        """Choose the zone the Stone Slinger helps this turn."""
        self._check_action(pid)
        if eid not in self.horn_zones(pid):
            raise GameError("The Stone Slinger can't reach that zone")
        self.players[pid].horn = eid
        self.log(f"{self.players[pid].name}'s Stone Slinger helps in {self.env(eid).name}")

    def end_actions(self, pid):
        """The player has finished step 2."""
        self._check_action(pid)
        self.action_order.pop(0)
        self._end_of_actions(pid)
        self._next_actor()

    def _end_of_actions(self, pid):
        """Idle pawns at home earn their bonus, then the next player acts."""
        p = self.players[pid]
        for pawn in p.pawns:
            if pawn.resting or pawn.used:
                continue
            if pawn.location == HOME:
                if pawn.info.get("idle_gold"):
                    p.gold += pawn.info["idle_gold"]
                    self.log(f"{p.name}'s {pawn.name} earns {pawn.info['idle_gold']} gold")
        for pawn in p.pawns:
            if pawn.location == TOWN and pawn.info.get("town_gold") and not pawn.resting:
                p.gold += pawn.info["town_gold"]
                self.log(f"{p.name}'s {pawn.name} earns {pawn.info['town_gold']} gold")

    # ---- 4. harvest ---------------------------------------------------------
    def _start_harvest(self):
        """Step 3 starts: list the zones with pawns, to be harvested one by one."""
        self.phase = "harvest"
        self.harvest_queue = [e.eid for e in self.envs if self.visitors(e.eid)]
        self.harvest_stage = "next"
        if not self.harvest_queue:
            self._end_turn()

    def visitors(self, eid):
        """Players present in an environment, in turn order."""
        return [pid for pid in self.order() if self.pawns_at(pid, eid)]

    def harvest_next(self):
        """Collect in the next environment and prepare its contest."""
        if self.phase != "harvest" or self.harvest_stage != "next":
            raise GameError("Not ready to harvest")
        eid = self.harvest_queue.pop(0)
        env = self.env(eid)
        present = self.visitors(eid)
        self.report = {"env": eid, "gathers": [], "rolls": [], "mob": None, "awards": [],
                       "wounds": [], "text": "", "stances": {}, "rerolls": 0}
        for pid in present:
            self._gather(pid, env)
        self._zone_dangers(env, present)
        present = [pid for pid in present if self.fighters(pid, eid)]  # Raiders alone don't contest
        self.contest = {"env": eid, "players": present, "stances": {}, "pending": list(present)}
        if not present:
            self.report["text"] = "Only Raiders here: nobody fights for the prize."
            self.harvest_stage = "report"
            return
        if len(present) == 1 and not env.mob:
            self.contest["stances"][present[0]] = (FIGHT, None)
            self.contest["pending"] = []
            self._resolve_contest()
        else:
            self.active = present[0]
            self.harvest_stage = "stance"

    def _gather(self, pid, env):
        """Each of the player's pawns in the zone collects its resource."""
        p = self.players[pid]
        pawns = self.pawns_at(pid, env.eid)
        for pawn in pawns:
            res = env.harvest[0]
            qty = 1 + (pawn.info.get("harvest_bonus", 1) if res in pawn.info.get("harvest", []) else 0)
            p.res[res] += qty
            self.report["gathers"].append((pid, res, qty, pawn.name))
        self._gather_events(pid, env, env.harvest[0], pawns)

    # ---- fight stances ------------------------------------------------------
    def stance_options(self, pid):
        """Options as (stance, target, label)."""
        present = self.contest["players"]
        if len(present) == 1:
            return [(FIGHT, None, "Fight the mob"), (YIELD, None, "Retreat")]
        options = [(FIGHT, None, "Fight for it")]
        if self.split_allowed():
            options.append((SPLIT, None, "Propose a split"))
        options.append((YIELD, None, "Retreat"))
        return options

    def split_allowed(self):
        """Once a player chose to fight, the next ones can only fight or retreat."""
        return all(stance != FIGHT for stance, _ in self.contest["stances"].values())

    def set_stance(self, pid, stance, target=None):
        """A player chooses to fight, split or retreat."""
        if self.harvest_stage != "stance" or pid != self.active:
            raise GameError("Not your choice")
        if stance not in [s for s, _, _ in self.stance_options(pid)]:
            raise GameError("You can't choose that now")
        self.contest["stances"][pid] = (stance, target)
        self.contest["pending"].remove(pid)
        if self.contest["pending"]:
            self.active = self.contest["pending"][0]
        else:
            self._resolve_contest()

    # ---- fight strength and dice --------------------------------------------
    def strength_parts(self, pid, eid, vs_mob, support=0):
        """Fight bonus as (label, value): every pawn gives +1, then abilities and buildings."""
        p = self.players[pid]
        pawns = self.fighters(pid, eid)
        # the Spearman adds nothing, and nor does a Stone Slinger that helped another zone
        counted = sum(1 for x in pawns if not x.info.get("no_strength") and not (x.info.get("horn") and p.horn))
        parts = [(f"{counted} pawn{'s' if counted != 1 else ''}", counted)]
        if support:
            parts.append(("Help from a player", support))
        for x in pawns:
            value = x.info.get("combat", 0) + (x.info.get("vs_mob", 0) if vs_mob else 0)
            if value:
                parts.append((x.name, value))
        keys = ("combat", "vs_mob") if vs_mob else ("combat", "vs_player")
        event = self.event_of(eid)
        for b in p.buildings:
            value = sum(D.BUILDINGS[b].get(k, 0) for k in keys)
            if value and event != "open_ground":
                parts.append((D.BUILDINGS[b]["name"], value))
        if event == "high_ground":
            parts.append(("High Ground", counted))
        elif event == "swamp_gas":
            strong = sum(1 for x in pawns
                         if x.info.get("combat", 0) + (x.info.get("vs_mob", 0) if vs_mob else 0))
            if strong:
                parts.append(("Swamp Gas", -strong))
        elif event == "ancient_knowledge" and self.first_here.get(eid) == pid:
            parts.append(("Ancient Knowledge", 1))
        elif event == "friendly_monster":
            friend = self.env(eid).friend
            if friend and friend[0] == pid:
                parts.append((f"Friendly {friend[1]}", friend[2]))
        if p.horn == eid and pawns and self.horn_zones(pid, check_target=False):
            parts.append(("Stone Slinger", 1))
        if p.has_effect("peasant_combat") and event != "open_ground":
            peasants = sum(1 for x in pawns if x.kind == "peasant")
            if peasants:
                parts.append(("Training Ground", peasants))
        if "weak" in self.challenge and not self.players[pid].is_ai:  # humans only
            parts.append(("Challenge", -1))
        return parts

    def strength(self, pid, eid, vs_mob, support=0):
        """The player's total fight strength in a zone (never below 0)."""
        return max(0, sum(v for _, v in self.strength_parts(pid, eid, vs_mob, support)))

    def dice_count(self, pid, eid):
        """How many dice the player rolls (best one counts)."""
        p = self.players[pid]
        return (1 + any(x.info.get("extra_die") for x in self.fighters(pid, eid))
                + (1 if p.has_effect("extra_die") else 0))

    def _roll(self, n):
        """Roll n six-sided dice."""
        return [self.rng.randint(1, 6) for _ in range(n)]

    # ---- fight results ------------------------------------------------------
    def _resolve_contest(self):
        """Everyone has chosen a stance: decide the fight, the split or who takes the prize."""
        c = self.contest
        env = self.env(c["env"])
        res, qty = env.prize
        report = self.report
        report["stances"] = dict(c["stances"])
        contenders = [p for p in c["players"] if c["stances"][p][0] != YIELD]
        support = {p: 0 for p in contenders}
        for pid in c["players"]:
            stance, target = c["stances"][pid]
            if stance == YIELD and target in support:
                support[target] += len(self.fighters(pid, c["env"]))
        prize_text = f"{qty} {res_name(res)}"
        pname = lambda pid: self.players[pid].name

        if not contenders:
            report["text"] = f"Everyone leaves. Nobody takes the {prize_text}."
        elif len(contenders) > 1 and all(c["stances"][p][0] == SPLIT for p in contenders):
            self._resolve_split(env, contenders, support)
        elif len(contenders) == 1 and not env.mob:
            got = self._award(contenders[0], res, qty, env, False)
            report["text"] = f"{pname(contenders[0])} takes {got} {res_name(res)} without a fight."
        else:
            self._resolve_fight(env, contenders, support)

        for pid, r, q in report["awards"]:
            self.add_res(pid, r, q)
        report["text"] = " ".join([report["text"]] + report.get("notes", []))
        self.contest = None
        self.harvest_stage = "report"
        self.log(f"{env.name}: {report['text']}")

    def _mob_roll(self, env):
        """The mob's roll: one die plus its strength."""
        if not env.mob:
            return None
        die = self._roll(1)[0]
        strength = env.mob[1]
        mob = {"name": env.mob[0], "strength": strength, "count": env.mob[1], "die": die,
               "score": die + strength}
        self.report["mob"] = mob
        return mob

    def _award(self, pid, res, qty, env, against_mob):
        """Give a fight's winner the prize, with event and building bonuses. Returns the amount."""
        p = self.players[pid]
        event = self.event_of(env.eid)
        if event == "trapped_relic":
            value = self.rng.randint(1, 6)
            self._event_die(pid, value != 1, value, "the bonus prize is lost!" if value == 1
                            else "the prize is safe (only a 1 loses it)")
            if value == 1:
                self._note("Trapped Relic: the bonus prize is lost!")
                return 0
        if env.extra_food:
            self.report["awards"].append((pid, "food", env.extra_food))
        if event in ("sunken_treasure", "forgotten_treasury"):
            self.report["awards"].append((pid, "gold", 2))
        elif event == "curse" and p.gold:
            p.gold -= 1
            self._note(f"Curse: {p.name} loses 1 gold.")
        elif event == "cursed_treasure":
            self.choices.append({"pid": pid, "kind": "curse", "env": env.eid,
                                 "why": "Cursed Treasure: choose your price"})
            self._note("Cursed Treasure: the winner must pay a price.")
        qty += max((x.info.get("prize_bonus", 0) for x in self.pawns_at(pid, env.eid)), default=0)
        if against_mob:
            qty += p.building_sum("mob_prize")
        self.report["awards"].append((pid, res, qty))
        return qty

    def _beaten_by_mob(self, pid, mob, eid):
        """Advanced game: what a mob does to a player it beats in zone eid."""
        if not self.mob_abilities:
            return ""
        p = self.players[pid]
        beaten = [x for x in self.fighters(pid, eid) if not x.leaving]
        if mob["name"] == "Gnolls":
            lost = min(p.gold, mob["count"])
            p.gold -= lost
            self.log(f"Gnolls take {lost} gold from {p.name}")
            return f" Gnolls take {lost} gold from {p.name}."
        if mob["name"] == "Snakes":
            pawns = [x for x in beaten if not x.wounded_next and not x.info.get("tough")]  # tough pawns resist
            if not pawns:
                return ""
            pawn = self.rng.choice(pawns)
            pawn.wounded_next = True
            self.report["wounds"].append((pid, pawn.name))
            return f" Snakes wound {p.name}'s {pawn.name}."
        if mob["name"] == "Spiders" and beaten:
            pawn = self.rng.choice(beaten)
            pawn.web_next = eid
            self.log(f"Spiders catch {p.name}'s {pawn.name} in their web")
            return f" Spiders catch {p.name}'s {pawn.name}: it stays here next turn."
        return ""

    def _beat_mob(self, pid, mob):
        """Advanced game: what a beaten mob leaves behind."""
        self.players[pid].note(f"beat_{mob['name']}", mob.get("count", 0), best=True)  # the strongest one beaten
        gift = {"Bears": "food", "Skeletons": "iron"}.get(mob["name"]) if self.mob_abilities else None
        if gift:
            self.report["awards"].append((pid, gift, 1))

    def _credit_win(self, pid, env):
        """A fight was won: pawns that fought and earn VP for it get them."""
        for pawn in self.fighters(pid, env.eid):
            gain = pawn.info.get("win_vp", 0)
            if gain:
                pawn.won_vp += gain
                self.players[pid].note(f"win_vp_{pawn.kind}", gain)
                self._note(f"{self.players[pid].name}'s {pawn.name} earns {gain} VP.")

    def _resolve_split(self, env, allies, support):
        """Everyone proposed a split. Against a mob, each player fights it alone,
        and only those who beat it share the prize."""
        report = self.report
        res, qty = env.prize
        mob = self._mob_roll(env)
        self.tie_note = ""
        winners = list(allies)
        start = ""
        if mob:
            winners = []
            for pid in allies:
                dice = self._roll(self.dice_count(pid, env.eid))
                strength = self.strength(pid, env.eid, True, support[pid])
                roll = {"pid": pid, "label": self.players[pid].name, "dice": dice,
                        "strength": strength, "score": max(dice) + strength}
                while roll["score"] == mob["score"]:  # a tie with the mob is rolled again
                    report["rerolls"] += 1
                    self.tie_note = f" Tied, rolled again ({report['rerolls']}x)."
                    roll["dice"] = self._roll(len(dice))
                    roll["score"] = max(roll["dice"]) + strength
                report["rolls"].append(roll)
                if roll["score"] > mob["score"]:
                    winners.append(pid)
            report["split_winners"] = list(winners)
            beaten = ""
            for pid in allies:
                if pid not in winners:
                    self._wound(pid, env)
                    beaten += self._beaten_by_mob(pid, mob, env.eid)
            if not winners:
                report["text"] = f"Defeated by {mob['name']}. The prize stays here.{self.tie_note}{beaten}"
                return
            names = " and ".join(self.players[p].name for p in winners)
            start = f"{names} beat{'s' if len(winners) == 1 else ''} {mob['name']}. "
            if len(winners) == 1:
                got = self._award(winners[0], res, qty, env, True)
                self._credit_win(winners[0], env)
                self._beat_mob(winners[0], mob)
                if self.event_of(env.eid) == "mountain_shrine":
                    report["awards"].append((winners[0], "gold", 2))
                report["text"] = f"{start}{names} takes {got} {res_name(res)}.{self.tie_note}{beaten}"
                return
        share, lost = divmod(qty, len(winners))
        for pid in winners:
            if mob:
                self._credit_win(pid, env)
                self._beat_mob(pid, mob)
            if share:
                report["awards"].append((pid, res, share))
            if env.extra_food // len(winners):
                report["awards"].append((pid, "food", env.extra_food // len(winners)))
            if mob and self.event_of(env.eid) == "mountain_shrine":
                report["awards"].append((pid, "gold", 2))
        result = f"Each gets {share} {res_name(res)}" if share else "Nobody gets any"
        note = f", and {lost} is lost" if share and lost else ""
        report["text"] = f"{start}{result}{note}.{self.tie_note}{beaten if mob else ''}"

    def _resolve_fight(self, env, contenders, support):
        """Roll the fight between players (and the mob) and give the prize to the best roll."""
        report = self.report
        res, qty = env.prize
        mob = self._mob_roll(env)
        rolls = []
        for pid in contenders:
            dice = self._roll(self.dice_count(pid, env.eid))
            strength = self.strength(pid, env.eid, bool(mob), support[pid])
            rolls.append({"pid": pid, "label": self.players[pid].name, "dice": dice,
                          "strength": strength, "score": max(dice) + strength})
        report["rolls"] = rolls
        best = self._settle(rolls, mob)
        if best is mob:
            report["text"] = f"Defeated by {mob['name']}. The prize stays here.{self.tie_note}"
            for pid in contenders:
                self._wound(pid, env)
                report["text"] += self._beaten_by_mob(pid, mob, env.eid)
            return
        winner = best["pid"]
        self._credit_win(winner, env)
        got = self._award(winner, res, qty, env, bool(mob))
        if mob:
            self._beat_mob(winner, mob)
        note = ""
        for pid in contenders:
            if pid == winner:
                continue
            if any(x.info.get("thief") for x in self.pawns_at(pid, env.eid)) and got > 1:
                report["awards"][-1] = (winner, res, got - 1)
                report["awards"].append((pid, res, 1))
                self.players[pid].note("thief_steals")
                got -= 1
                note += f" {self.players[pid].name}'s Thief steals 1."
            self._wound(pid, env)
        if self.event_of(env.eid) == "mountain_shrine":
            report["awards"].append((winner, "gold", 2))
        report["text"] = f"{self.players[winner].name} wins {got} {res_name(res)}.{self.tie_note}{note}"

    def _settle(self, rolls, mob):
        """Everyone tied for the top score rolls again until one side is ahead."""
        self.tie_note = ""
        while True:
            sides = rolls + ([mob] if mob else [])
            top = max(side["score"] for side in sides)
            tied = [side for side in sides if side["score"] == top]
            if len(tied) == 1:
                return tied[0]
            self.report["rerolls"] += 1
            self.tie_note = f" Tied, rolled again ({self.report['rerolls']}x)."
            for side in tied:
                if side is mob:
                    side["die"] = self._roll(1)[0]
                    side["score"] = side["die"] + side["strength"]
                else:
                    side["dice"] = self._roll(len(side["dice"]))
                    side["score"] = max(side["dice"]) + side["strength"]

    def _wound(self, pid, env):
        """After a lost fight, the pawns that fought miss the next turn."""
        for pawn in self.woundable(pid, env.eid, fight=True):
            pawn.wounded_next = True
            self.report["wounds"].append((pid, pawn.name))

    def ack_report(self):
        """The harvest report of a zone was read: go on."""
        if self.harvest_stage != "report":
            raise GameError("No report to close")
        self.report = None
        self._after_choices()

    # ---- end of turn and game -----------------------------------------------
    def _end_turn(self):
        """Pawns that left are removed, then a new turn starts or the game ends."""
        self.harvest_stage = None
        for p in self.players:
            p.pawns = [x for x in p.pawns if not x.leaving]
            self.vp_history[p.pid].append(self.victory_points(p.pid)[4])
        if D.ROTATE_FIRST_PLAYER:
            self.first = (self.first + 1) % len(self.players)
        if self.turn >= self.max_turns:
            self._finish()
        else:
            self.start_turn()

    def leftover_value(self, p):
        """The gold a player's unsold resources are worth at the end of the game."""
        total = 0
        for r, n in p.res.items():
            base = D.RESOURCES[r][1]
            if p.has_effect("full_leftovers"):
                total += base * n
            else:
                total += base * n / 2
        return int(total)

    def pawn_points(self, pawn):
        """What this pawn is worth now, with the VP it has earned."""
        return D.pawn_vp(pawn.kind) + pawn.won_vp

    def victory_points(self, pid):
        """Returns (building VP, pawn VP, gold counted, VP from gold, total VP)."""
        p = self.players[pid]
        buildings = sum(D.building_vp(b) for b in p.buildings)
        pawns = sum(self.pawn_points(x) for x in self.staying(pid))
        coins = p.gold + self.leftover_value(p)
        from_gold = coins // D.GOLD_PER_VP
        return buildings, pawns, coins, from_gold, buildings + pawns + from_gold

    def _finish(self):
        """The end: sell what is left, convert gold to VP and rank the players."""
        self.phase = "end"
        results = []
        for p in self.players:
            buildings, pawns, coins, from_gold, total = self.victory_points(p.pid)
            lines = [("Buildings", buildings), ("Pawns", pawns), ("Gold", from_gold)]
            results.append({"pid": p.pid, "name": p.name, "lines": lines, "total": total, "coins": coins})
        results.sort(key=lambda r: (-r["total"], -r["coins"]))
        self.final = results
        self.log(f"Game over. {results[0]['name']} wins with {results[0]['total']} VP!")
