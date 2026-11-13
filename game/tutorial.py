"""The tutorial: Sir Pebble walks a new player through one scripted turn."""
import math
import sys

import pygame

import ai
import art
import data as D
from engine import FIGHT, TOWN, Game
from screen import draw

GUIDE = ("guide", "yellow")  # the Black Knight, with a plain shield, explains the rules
GUIDE_NAME = "Sir Pebble"
HIGHLIGHT = (255, 236, 120)
START_BUILDING = "farm"
AI_BUILDING = "quarry"  # the AI's own building from the start
AI_RECRUIT = "bard"     # the Porter, which the AI buys in town
ZONE = "plains"         # where you beat the monster: it gives a lot of basic resources
ZONE_GIVES = "wood"     # what each pawn there collects
ZONE_PRIZE = ("stone", 4)  # its bonus prize...
ZONE_FOOD = 4              # ...with this much Food on top
AI_DELAY = 1.8  # seconds before each move of the computer, to watch it
TURNS = 4  # the tutorial is turn 1; Finish the game plays the other 3 normally


# ---- a game with scripted dice ----------------------------------------------
class TutorialGame(Game):
    """One turn with fixed dice: you beat the monster, then lose a fight against the computer.
    Once free (Finish the game), it is a normal game for the turns that are left."""

    def __init__(self, players):
        """A normal game with a fixed seed; script holds the dice values to roll next."""
        super().__init__(players, turns=TURNS, seed=11)
        self.script = []
        self.over = False
        self.free = False
        self.no_achievements = True  # the tutorial's scripted turn makes them too easy

    def _roll(self, n):
        """Roll the next scripted value, or real dice when the script is empty."""
        if self.script:
            value = self.script.pop(0)
            return [value] * n
        return super()._roll(n)

    def _resolve_fight(self, env, contenders, support):
        """Script the two fights: a sure win against the monster, then a loss by 1 against the AI."""
        if self.free:
            return super()._resolve_fight(env, contenders, support)
        you = self.strength(0, env.eid, bool(env.mob), support.get(0, 0)) if 0 in contenders else 0
        if env.mob and contenders == [0]:  # a sure win against the monster
            mob_score = 1 + env.mob[1]
            self.script = [1, min(6, max(1, mob_score + 2 - you))]
        elif not env.mob and sorted(contenders) == [0, 1]:  # AI wins by one point
            them = self.strength(1, env.eid, False, support.get(1, 0))
            your_die = 2
            their_die = your_die + you + 1 - them
            if their_die > 6:
                your_die, their_die = max(1, your_die - (their_die - 6)), 6
            dice = {0: your_die, 1: max(1, their_die)}
            self.script = [dice[pid] for pid in contenders]
        super()._resolve_fight(env, contenders, support)
        self.script = []

    def _start_harvest(self):
        """Harvest the monster's zone first, so the fights come in the order the guide explains."""
        super()._start_harvest()
        if not self.free:
            self.harvest_queue.sort(key=lambda eid: not self.env(eid).mob)  # the monster first

    def _end_turn(self):
        """The tutorial stops after one turn, with the board as it is."""
        if self.free:
            return super()._end_turn()
        self.harvest_stage = None
        self.phase = "tutorial_done"
        self.over = True


# ---- the guide, step by step ------------------------------------------------
class Tutorial:
    """Sir Pebble's guided first game: a list of steps, each with a text, highlighted places and a condition to
    move on."""
    def __init__(self, app):
        """Set up the tutorial game: you against one AI, with a Farm, 4 Peasants and a monster nearby."""
        self.app = app
        self.M = sys.modules[type(app).__module__]  # main's colors and sizes
        name = app.names[0].strip() or "Player 1"
        g = TutorialGame([(name, False), ("AI", True)])
        g.players[0].color = D.PLAYER_COLORS[0][1]
        g.players[0].team = "red"
        g.players[1].color = D.PLAYER_COLORS[1][1]
        g.players[1].team = "blue"
        g.players[0].buildings.append(START_BUILDING)  # one already built, to compare in the tree
        g.players[1].buildings.append(AI_BUILDING)
        g.add_pawn(0, "peasant")  # you start with 4 pawns
        g.add_pawn(0, "peasant")
        self.game = g
        self.zone = self.pick_zone()
        self.duel = next(e for e in g.envs if e is not self.zone)  # where you meet AI
        self.reported = set()  # zones whose fight has been shown
        self.timer = 0.0
        self.index = 0
        self.buttons = []
        self.allowed = None
        self.hurt = False
        self.steps = self.make_steps()

    # ---- setup --------------------------------------------------------------
    def pick_zone(self):
        """The Plains get a weak monster this turn, and give a lot of Wood, Stone and Food.
        Without Plains on the board, the zone with the weakest monster."""
        g = self.game
        best = None
        plains = next((e for e in g.envs if e.eid == ZONE), None)
        if plains:
            for other in g.envs:
                other.mob = None
            mob = min(D.zone_mobs(ZONE, 2), key=lambda m: m[1])
            plains.mob = (mob[0], min(mob[1], 3))
            plains.harvest, plains.prize, plains.extra_food = [ZONE_GIVES], ZONE_PRIZE, ZONE_FOOD
            return plains
        for env in g.envs:
            mobs = D.zone_mobs(env.eid, 2)
            if mobs:
                weakest = min(mobs, key=lambda m: m[1])
                if best is None or weakest[1] < best[1][1]:
                    best = (env, weakest)
        env, mob = best
        for other in g.envs:
            other.mob = None
        env.mob = (mob[0], min(mob[1], 3))
        return env

    # ---- what the player can see --------------------------------------------
    def base(self, pid):
        """The rectangle of a player's realm on the board."""
        return self.app.base_rects()[pid]

    def cell(self, key):
        """The rectangle of a zone (or the Town) on the board."""
        return self.app.env_cells()[key]

    def buttons_named(self, *labels):
        """The rectangles of the buttons drawn with these labels."""
        rects = self.app.button_rects
        return [rects[label] for label in labels if label in rects]

    def pawns(self, pid, location):
        """A player's pawns at a place."""
        return self.game.pawns_at(pid, location)

    def make_steps(self):
        """Every step of the tutorial, in order: what Sir Pebble says, what to highlight, when to go on."""
        g = self.game
        zone = self.zone.name
        mob = self.zone.mob[0]
        duel = self.duel.name
        M = self.M
        top_buttons = lambda: self.buttons_named("Buildings", "Zones", "Rules")
        build_box = pygame.Rect(20, 60, M.W - 40, M.H - 76)
        town_box = pygame.Rect(70, 44, M.W - 140, M.H - 88)
        sell_box = pygame.Rect(town_box.x + 576, town_box.y + 46, town_box.right - town_box.x - 586, town_box.h - 52)
        recruit_box = pygame.Rect(town_box.x + 10, town_box.y + 46, 560, town_box.h - 52)
        strip = lambda: pygame.Rect(self.base(0).x + 6, self.base(0).bottom - 52, self.base(0).w - 12, 46)
        header = lambda: pygame.Rect(self.base(0).x + 4, self.base(0).y + 4, self.base(0).w - 8, 86)

        def placed_ai():
            """How many pawns the AI has sent so far."""
            return sum(1 for x in g.players[1].pawns if x.placed)

        def kinds():
            """One building of each kind: owned, ready to build, too expensive, locked."""
            nodes = self.app.tree_nodes(pygame.Rect(20, 16, M.W - 40, M.H - 32))
            early = sorted(nodes, key=lambda b: D.BUILDINGS[b]["tier"])
            pick = lambda test: next((b for b in early if test(b)), None)
            found = {
                "owned": pick(lambda b: b in g.players[0].buildings),
                "ready": pick(lambda b: g.can_build(0, b)[0]),
                "costly": pick(lambda b: b not in g.players[0].buildings and not g.missing_requirements(0, b)
                               and not g.can_pay_for(0, b)),
                "locked": pick(lambda b: g.missing_requirements(0, b)),
            }
            return {k: nodes[b] for k, b in found.items() if b}

        def tree_marks():
            """What to highlight in the building tree: your buildings, the ready ones, the rest."""
            nodes = self.app.tree_nodes(pygame.Rect(20, 16, M.W - 40, M.H - 32))
            ready = [r for b, r in nodes.items() if g.can_build(0, b)[0]]  # every building you can build now
            return [pygame.Rect(34, 88, 204, M.STOCK_H)] + [r for r in kinds().values() if r not in ready] + ready

        def built():
            """True once you have built something new."""
            return len(g.players[0].buildings) > 1  # more than the one you started with

        steps = [
            dict(title="Welcome to Tiny Realms!",
                 text=f"Hello, I'm {GUIDE_NAME}, and I'll teach you how to rule a tiny realm. Ready? Let's go!"),
            dict(title="Your realm",
                 text="Today you play against AI, a computer player. This is your realm. You start with 4 pawns, "
                      "a little gold and a few resources. Hover a building to read what it does.",
                 targets=lambda: [self.base(0)]),
            dict(title="The zones",
                 text="In the middle are the zones. Each turn, they show two rewards: Each pawn collects one "
                      "resource automatically, while the Bonus goes to the zone's winner. Watch out! Monsters may "
                      "guard the bonus.",
                 targets=lambda: [self.cell(e.eid) for e in g.envs]),
            dict(title="The Town",
                 text="The Town is special. A pawn in town can sell your resources and recruit one new "
                      "pawn. You can only recruit once per turn.",
                 targets=lambda: [self.cell(TOWN)]),
            dict(title="Prices",
                 text="Down here: today's prices, in gold. They change every turn, so sell when they are high! "
                      "Green is more than usual, red is less.",
                 targets=lambda: [pygame.Rect(M.SIDE_W + 8, M.H - 6 - M.PRICE_H, M.W - 2 * M.SIDE_W - 16, M.PRICE_H)]),
            dict(title="Your opponent",
                 text="And this is AI. You can see its gold, resources, buildings and pawns too. Keep an eye on it!",
                 targets=lambda: [self.base(1)]),
            dict(title="Step 1: Send pawns",
                 text=f"Players take turns placing one pawn at a time. Click one of your pawns, then click the "
                      f"{zone}. {mob} guard its bonus prize: let's go and beat them!",
                 targets=lambda: [self.cell(self.zone.eid)],
                 allow=lambda: [strip(), self.cell(self.zone.eid)],
                 done=lambda: bool(self.pawns(0, self.zone.eid))),
            dict(title="Well done!",
                 text=f"Now it's AI's turn. Watch: it sends a pawn to the {duel}.",
                 targets=lambda: [self.cell(self.duel.eid)], allow=list,
                 ready=lambda: placed_ai() >= 1),
            dict(title="Challenge AI",
                 text=f"AI wants the bonus prize of the {duel}. Don't let it take it for free: send a pawn "
                      "there too!",
                 targets=lambda: [self.cell(self.duel.eid)],
                 allow=lambda: [strip(), self.cell(self.duel.eid)],
                 done=lambda: bool(self.pawns(0, self.duel.eid))),
            dict(title="Brave!",
                 text="AI plays again. It sends its other pawn to the Town.",
                 targets=lambda: [self.cell(TOWN)], allow=list,
                 ready=lambda: placed_ai() >= 2),
            dict(title="Your turn again",
                 text="Send a pawn to the Town. In step 2, it will sell your resources and recruit a new pawn.",
                 targets=lambda: [self.cell(TOWN)],
                 allow=lambda: [strip(), self.cell(TOWN)],
                 done=lambda: bool(self.pawns(0, TOWN))),
            dict(title="Stay home",
                 text="Keep your last pawn at home: in step 2, pawns at home build. Click Keep pawn home.",
                 targets=lambda: self.buttons_named("Keep pawn home"),
                 allow=lambda: self.buttons_named("Keep pawn home") + [strip()],
                 done=lambda: g.phase != "deploy"),
            dict(title="Step 2: Build and trade",
                 text="Great placing! Now your pawn at home can build one building, and your pawn in town can "
                      "sell and recruit. First, click Build.",
                 targets=lambda: self.buttons_named("Build"),
                 allow=lambda: self.buttons_named("Build"),
                 done=lambda: self.app.modal == "build"),
            dict(title="Choose a building",
                 text="Your resources are on the left. Light green: already owned. Green border: ready to "
                      "build. Red costs: not enough resources. Hover to see what a building does, then click one "
                      "with a green border!",
                 targets=tree_marks, allow=lambda: [build_box], where="right",
                 done=lambda: bool(built())),
            dict(title="Your first building!",
                 text="Congratulations, it's yours. Now let's go shopping: click Town.",
                 targets=lambda: self.buttons_named("Town"),
                 allow=lambda: self.buttons_named("Town"),
                 done=lambda: self.app.modal == "town"),
            dict(title="Sell",
                 text="Here, you sell resources for gold. Remember: prices change every turn! Choose what to sell "
                      "with + and -, then click Sell selected.",
                 targets=lambda: [sell_box], where="left",
                 allow=lambda: [sell_box],
                 done=lambda: any(x.sold for x in self.pawns(0, TOWN))),
            dict(title="Recruit",
                 text="Excellent! Now spend your gold on a new pawn. You can recruit only once per turn, so "
                      "choose well!",
                 targets=lambda: [recruit_box], allow=lambda: [recruit_box], where="right",
                 done=lambda: len(g.players[0].pawns) > 4),
            dict(title="Welcome aboard!",
                 text="Your new pawn joins your realm and will play next turn. You've done everything for this "
                      "step: click End.",
                 targets=lambda: self.buttons_named("End"),
                 allow=lambda: None if self.app.modal == "end_check" else self.buttons_named("End"),
                 done=lambda: g.phase != "actions" or g.active != 0),
            dict(title="Step 3: Harvest and fight",
                 text=f"Your pawns have collected their resources. Now for the bonus prizes! In the {zone}, {mob} "
                      "guard the prize. Beat the monsters to win the prize. Click Fight the mob!",
                 targets=lambda: self.buttons_named("Fight the mob", "Retreat"),
                 allow=lambda: self.buttons_named("Fight the mob"), width=320, where="left",
                 done=lambda: self.zone.eid in self.reported),
            dict(title="Victory!", text=self.mob_text, width=320, where="left",
                 targets=lambda: self.buttons_named("Continue") if self.app.report_time > self.M.FIGHT_TIME else [],
                 allow=lambda: self.buttons_named("Continue"),
                 done=lambda: self.zone.eid in self.reported and not (g.report and g.report["env"] == self.zone.eid)),
            dict(title="Fight against AI",
                 text=f"In the {duel}, AI wants the prize too! You choose first: Fight for it!",
                 targets=lambda: self.buttons_named("Fight for it", "Propose a split", "Retreat"),
                 allow=lambda: self.buttons_named("Fight for it"), width=320, where="left",
                 done=lambda: self.duel.eid in self.reported),
            dict(title="The fight", text=self.fight_text, width=320, where="left",
                 targets=lambda: self.buttons_named("Continue") if self.app.report_time > self.M.FIGHT_TIME else [],
                 allow=lambda: self.buttons_named("Continue"),
                 done=lambda: g.over),
            dict(title="End of the turn",
                 text="Look at your resources: your pawns brought back what they collected.",
                 targets=lambda: [header()], enter=self.show_wounds),
            dict(title="At the end of the game",
                 text="Resources you still have at the end are sold automatically, but at half price. Then "
                      "every 5 gold gives 1 VP. So it's better to use or sell them before!",
                 targets=lambda: [header()]),
            dict(title="Need help?",
                 text="Up here, the Buildings button: it shows the whole building tree. Rules explain all the "
                      "rules. The Zones button gives you extra information about the game, but it's not the most "
                      "important thing to remember for a first game.",
                 targets=top_buttons, allow=lambda: None, where="bottom"),
            dict(title="Congratulations!",
                 text="You finished the tutorial! You now know how to send pawns, build, trade and fight. "
                      "You're ready to rule your own realm. Good luck, and have fun!", final=True),
        ]
        return steps

    def rolled(self):
        """The scores of the fight on screen, once the dice have stopped."""
        report = self.game.report
        if not report or self.app.report_time < self.M.FIGHT_TIME:
            return None
        scores = {r["pid"]: r["score"] for r in report["rolls"]}
        return scores, report["mob"]

    def mob_text(self):
        """Sir Pebble's comment on the fight against the monster, once the dice are rolled."""
        rolled = self.rolled()
        if not rolled or 0 not in rolled[0] or not rolled[1]:
            return "Here come the dice..."
        scores, mob = rolled
        return (f"Bravo! You scored {scores[0]} and the {mob['name']} scored {mob['score']}: the bonus prize "
                "is yours! Click Continue.")

    def fight_text(self):
        """Sir Pebble's comment on the fight against the AI, once the dice are rolled."""
        rolled = self.rolled()
        if not rolled or not {0, 1} <= set(rolled[0]):
            return "Here come the dice..."
        scores = rolled[0]
        return (f"Oh no! You scored {scores[0]}, but AI scored {scores[1]}. You lost against AI, so your pawn "
                "there is wounded and misses the next turn. Click Continue.")

    def show_wounds(self):
        """Wounded pawns are drawn gray, as they will be next turn."""
        for p in self.game.players:
            for x in p.pawns:
                if x.wounded_next:
                    x.resting = True

    # ---- flow ---------------------------------------------------------------
    @property
    def step(self):
        """The current step."""
        return self.steps[self.index]

    def next_step(self):
        """Go to the next step and run its 'enter' action."""
        if self.index < len(self.steps) - 1:
            self.index += 1
            enter = self.step.get("enter")
            if enter:
                enter()

    def update(self, dt):
        """Each frame: remember reports, move on when the step's condition is met, let the AI play."""
        g = self.game
        if g.harvest_stage == "report" and g.report:
            self.reported.add(g.report["env"])
        while self.step.get("done") and self.step["done"]():
            self.next_step()
        self.drive_ai(dt)

    def drive_ai(self, dt):
        """AI's moves are part of the lesson."""
        g = self.game
        if g.over or g.active != 1 or self.app.modal:
            self.timer = 0.0
            return
        waiting = (g.phase in ("deploy", "actions") or g.harvest_stage in ("stance", "choice"))
        if not waiting:
            return
        self.timer += dt
        if self.timer < AI_DELAY:
            return
        self.timer = 0.0
        if g.phase == "deploy":
            pawn = g.deployable(1)[0]
            target = self.duel.eid if not self.pawns(1, self.duel.eid) else TOWN
            g.send(1, pawn.uid, target)
        elif g.phase == "actions":
            if g.pawns_at(1, TOWN) and g.free_town(1) and AI_RECRUIT not in [x.kind for x in g.players[1].pawns]:
                offers = g.recruits[1]
                if AI_RECRUIT not in offers:
                    offers[0] = AI_RECRUIT  # only the AI's own copy of the offers
                index = offers.index(AI_RECRUIT)
                g.players[1].gold = max(g.players[1].gold, g.recruit_cost(1, index))
                g.recruit(1, index)
            else:
                g.end_actions(1)
        elif g.harvest_stage == "stance":
            g.set_stance(1, FIGHT)
        elif g.harvest_stage == "choice":
            g.choose(1, g.choice_options()[0][0])

    # ---- input --------------------------------------------------------------
    def click(self, pos):
        """A click on the guide's own buttons (Next, Quit tutorial...). True if one was hit."""
        for rect, action in self.buttons:
            if rect.collidepoint(pos):
                action()
                return True
        return False

    def allows(self, pos):
        """During a step, only clicks on its highlighted places reach the game."""
        if self.allowed is None:
            return True
        return any(r.collidepoint(pos) for r in self.allowed)

    def quit(self):
        """Quit tutorial asks first (see app.App.draw_exit_confirm)."""
        self.app.confirm_exit = "tutorial"

    def finish(self):
        """Finish the game: the guide leaves and the game goes on normally against the AI."""
        g, app = self.game, self.app
        g.free, g.over = True, False
        g.brains[1] = ai.load_for(8, 2, False)  # the shortest trained game
        app.tutorial = None  # the AI now plays by itself, and every click reaches the game
        app.modal = None
        Game._end_turn(g)  # on to turn 2

    def play(self):
        """End of the tutorial: go to the game choice page."""
        self.app.back_to_menu()
        self.app.page = "mode"

    # ---- drawing ------------------------------------------------------------
    def draw(self):
        """Draw the dark veil with holes on the highlighted places, the guide and his speech bubble."""
        app, M = self.app, self.M
        step = self.step
        targets = [pygame.Rect(r) for r in (step["targets"]() if step.get("targets") else [])]
        allow = step.get("allow")
        self.allowed = allow() if allow else []  # None lets every click through
        if app.modal in M.VIEWERS:  # Zones, Buildings or Rules: the guide waits until it is closed
            self.allowed = None
            self.buttons = []
            return
        if app.confirm_exit:
            targets = []  # a question is open: it is already the only lit thing on screen
        if targets:
            self.spotlight(targets)
        pulse = 0.5 + 0.5 * math.sin(app.clock_time * 5)
        for rect in targets:
            box = rect.inflate(8, 8)
            draw.rect(app.canvas, HIGHLIGHT, box, 3 + int(2 * pulse), border_radius=10)
        self.draw_bubble(step, targets)

    def spotlight(self, targets):
        """Darken everything but what the guide talks about."""
        canvas = self.app.canvas
        key = (canvas.get_size(), tuple(tuple(r) for r in targets))
        if getattr(self, "veil_key", None) != key:  # made once per step, not every frame
            layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            layer.fill((10, 6, 4, 120))
            for rect in targets:
                area = canvas.rect(rect.inflate(8, 8))
                pygame.draw.rect(layer, (0, 0, 0, 0), area, border_radius=round(10 * canvas.scale))
            self.veil, self.veil_key = layer, key
        pygame.Surface.blit(canvas, self.veil, (0, 0))

    def bubble_rect(self, step, height, width, targets):
        """Where to put the speech bubble so it hides none of the highlighted places."""
        M = self.M
        spots = {
            "bottom": (M.W // 2 - width // 2, M.H - height - 70),
            "top": (M.W // 2 - width // 2, 52),
            "middle": (M.W // 2 - width // 2, M.H // 2 - height // 2),
            "left": (10, M.H - height - 10),
            "right": (M.W - width - 10, M.H - height - 56),
        }
        order = ["bottom", "middle", "top", "left", "right"]
        if step.get("where"):
            order.insert(0, step["where"])
        for key in order:
            rect = pygame.Rect(spots[key], (width, height))
            if not any(rect.colliderect(t.inflate(10, 10)) for t in targets):
                return rect
        return pygame.Rect(spots[order[0]], (width, height))

    def draw_bubble(self, step, targets):
        """The speech bubble with its text and buttons."""
        app, M = self.app, self.M
        width = step.get("width", 600)
        narrow = width < 400
        text = step["text"]() if callable(step["text"]) else step["text"]
        text_w = width - 40 if narrow else width - 150
        lines = app.wrap(text, text_w, 15)
        guide_h = 96 if narrow else 0
        show_next = step.get("final") or (not step.get("done") and step.get("ready", lambda: True)())
        height = max(150 if show_next or not narrow else 0, 56 + guide_h + len(lines) * 20 + (56 if show_next else 10))
        rect = self.bubble_rect(step, height, width, targets)
        app.canvas.shade(rect.move(4, 5), (0, 0, 0, 90), 12)
        draw.rect(app.canvas, M.CREAM, rect, border_radius=12)
        draw.rect(app.canvas, M.ACCENT, rect, 3, border_radius=12)
        frame = int(app.clock_time * 8)
        if narrow:
            app.draw_unit(*GUIDE, app_anim(), frame, rect.x + 60, rect.y + 104, 92)
            app.text(GUIDE_NAME, (rect.x + 112, rect.y + 64), 13, M.MUTED, True, "midleft")
            tx, ty = rect.x + 20, rect.y + 112
        else:
            app.draw_unit(*GUIDE, app_anim(), frame, rect.x + 66, rect.y + 116, 100)
            app.text(GUIDE_NAME, (rect.x + 66, rect.y + 132), 12, M.MUTED, True, "center")
            tx, ty = rect.x + 130, rect.y + 16
        app.text(step["title"], (tx, ty), 20, M.ACCENT, True)
        y = ty + 32
        for line in lines:
            app.text(line, (tx, y), 15, M.INK)
            y += 20
        self.buttons = []
        bottom = rect.bottom - 46
        quit_rect = pygame.Rect(M.W - 150, M.H - 46, 140, 36)  # the empty bottom-right corner
        if step.get("final"):
            self.add_button(pygame.Rect(rect.right - 174, bottom, 160, 34), "Play a game", self.play, True)
            self.add_button(pygame.Rect(rect.right - 360, bottom, 176, 34), "Finish the game", self.finish, False)
            return
        self.add_button(quit_rect, "Quit tutorial", self.quit, False, 13)
        if show_next:  # Next once AI has moved
            self.add_button(pygame.Rect(rect.right - 134, bottom, 120, 34), "Next", self.next_step, True)

    def add_button(self, rect, label, action, primary, size=15):
        """A button in the bubble, clickable even when the game's clicks are blocked."""
        self.app.button(rect, label, action, primary=primary, size=size)
        self.buttons.append((rect, action))


def app_anim():
    """The guide's animation (standing)."""
    return art.IDLE
