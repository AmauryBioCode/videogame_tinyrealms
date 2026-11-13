"""Tiny Realms: the window, the menu and every screen. Start the game with  python main.py  (one folder up)."""
import asyncio
import math
import os
import random
import sys
import traceback

try:
    import pygame
except ImportError:
    print("Pygame is missing. Install it with:  python -m pip install pygame-ce")
    sys.exit(1)

WEB = sys.platform == "emscripten"  # the browser version (built with pygbag for itch.io)

import achievements
import ai
import paths
import art
import data as D
import settings
import sound
from engine import FIGHT, HOME, SPLIT, TOWN, Game, res_name
from screen import Screen, draw

# ---- sizes and colors -------------------------------------------------------
W, H = 1280, 800
TOP_H = 44
SIDE_W = 300
PRICE_H = 54  # the market prices under the zones
CELL_H = (H - TOP_H - 6 - 12 - 6 - PRICE_H - 6) // 3  # the zones share what is left
INK = (48, 34, 26)
PAPER = (244, 232, 206)
PAPER_DARK = (222, 204, 170)
TABLE = (88, 58, 38)
TABLE_DARK = (66, 42, 28)
BORDER = (16, 10, 6)  # the thin strips when the screen is not 16:10
ACCENT = (204, 138, 36)
ACCENT_LIGHT = (240, 178, 66)
GOOD = (70, 150, 84)
BAD = (186, 58, 50)
BAD_LIGHT = (255, 150, 130)
MUTED = (132, 112, 92)
CREAM = (255, 248, 232)

# ---- timing, steps and rules text -------------------------------------------
FIGHT_TIME = 1.5  # seconds of fight animation before the result
END_FADE, END_TITLE, END_ROW, END_GRAPH = 1.2, 1.0, 0.8, 1.5  # seconds of the transition to the final scores
MAX_NAME = 12
STEPS = [("deploy", "Send pawns"), ("actions", "Build and trade"), ("harvest", "Harvest and fight")]
RULES = [
    ("Goal", "Have the most victory points (VP) at the end of the game."),
    ("Dawn", "Buildings produce resources. Each zone reveals a random resource, a bonus prize and sometimes "
             "a mob. Market prices change."),
    ("1. Send pawns", "Take turns sending one pawn at a time to a zone or town. You can send only one pawn to "
                      "town. Unsent pawns stay home. The first player changes each turn."),
    ("2. Build and trade", "• Home: Each pawn can build one building.\n"
                           "• Town: Your pawn can recruit one pawn and sell resources as often as you like, in "
                           "any order.\n"
                           "Recruits appear after everyone has placed their pawns. All players see the same "
                           "recruits and can buy them, even if someone else already has.\n"
                           "You can have up to 8 pawns (9 with the Guild Hall). If you recruit beyond this "
                           "limit, choose a pawn to replace.\n"
                           "Press End when finished. Resources collected during Harvest can only be used next "
                           "turn."),
    ("3. Harvest", "• Resource: Every pawn collects 1 of the resource shown under \u201cEach pawn\u201d.\n"
                   "• Bonus prize: Players compete for it or agree to share it.\n"
                   "If you're alone against a mob, fight or retreat. If other players are present, the first "
                   "player chooses to fight, offer a split or retreat. Once someone chooses to fight, everyone "
                   "else must fight or retreat."),
    ("Fights", "Your score is your best die roll + fight bonus.\n"
               "Each pawn adds +1 strength, plus any bonuses from abilities and buildings. Your total appears "
               "on the zone's Fight bonus line.\n"
               "The highest score wins, but must also beat the mob if present. Ties are rerolled until "
               "someone wins."),
    ("Splits", "If all remaining players agree, they share the prize equally. Any leftover is lost.\n"
               "If a mob is present, each player fights it separately:\n"
               "• All win: share the prize.\n"
               "• Only one wins: that player takes everything.\n"
               "• Several win, but not all: the winners share the prize.\n"
               "If anyone chooses to fight instead of split, a fight begins."),
    ("Wounds", "Losing a fight wounds all your participating pawns. They miss the next turn.\n"
               "Lancers, Black Knights and Healers can prevent wounds. The Infirmary heals one wounded pawn "
               "of your choice at the end of each turn.\n"
               "Retreating causes no wounds."),
    ("Mobs", "• Turn 1: No mobs.\n"
             "• Turn 2: At most 1 mob.\n"
             "• Later: At most 2 mobs on the board.\n"
             "With 3 players, each zone's strongest mob is excluded. With 4 players, its two strongest mobs "
             "are excluded."),
    ("Buildings", "You can own one of each building. Most require another building first.\n"
                  "Open Buildings to see the upgrade tree.\n"
                  "The Workshop's discount adds to the Mason's or the Dwarf Builder's, but the Mason and the "
                  "Dwarf Builder can't both lower the same building."),
    ("End of game", "Your final score includes:\n"
                    "• Buildings: VP shown in the building tree.\n"
                    "• Pawns: 0 VP for Peasants, 1\u20134 VP for others, plus any VP earned by War Rams.\n"
                    "• Gold: 1 VP for every 5 gold.\n"
                    "Unsold resources count as gold at half their base price.\n"
                    "If players tie, the one with the most gold wins."),
]


FONT_FILES = {False: "Inter-Regular.otf", True: "Inter-Bold.otf"}  # in assets/fonts, for the browser


def load_font(size, bold=False):
    """A rounded system font, with fallbacks for Mac, Windows and Linux. A browser has none of them,
    so the browser version uses the Inter font that comes with the game."""
    if WEB:
        path = os.path.join(art.ROOT, "fonts", FONT_FILES[bool(bold)])
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont("avenirnext,helveticaneue,helvetica,arial,dejavusans", size, bold=bold)


VIEWERS = ("rules", "catalog", "zones", "settings")
SHAPES = {"red": "circle", "blue": "square", "yellow": "triangle", "purple": "hexagon"}  # under each player's pawns
COLORS = {name.lower(): color for name, color in D.PLAYER_COLORS}
# with the colorblind help on: colors that stay apart for every kind of colorblindness (Okabe and Ito)
COLORBLIND = {"red": (213, 94, 0), "blue": (0, 114, 178), "yellow": (230, 159, 0), "purple": (204, 121, 167)}  # windows that pause the game
# the Credits page (the same as assets/CREDITS.txt)
# each line is plain text, or (text, link): the link is shown after the text and opens in the browser
CREDITS = [
    ("Game", ["A game by AmauryBioCode", "Made with Python and pygame-ce"]),
    ("Art", ["Characters, monsters, zones, home ground, menu picture and interface pieces:",
             ("Tiny Swords by Pixel Frog - ", "pixelfrog-assets.itch.io/tiny-swords"),
             ("Inventory icons by o_HET - ",
              "o-het.itch.io/576-fantasy-survival-rpg-inventory-icons-pixel-art-crafting-loot-weapons-resou"),
             ("Interface: UI MEGA PACK by ToffeeCraft - ", "toffeecraft.itch.io/ui-user-interface-mega-pack"),
             ("Iron and gem icons by Filwarka - ", "filwarka.itch.io/2d-roblox-resources-icons-asset"),
             ("Stone, gold and chest icons by sownddddd - ",
              "sownddddd.itch.io/free-medieval-fantasy-rpg-game-icon-pack-46-icons-grayscale"),
             "Buildings: made with an AI image generator (Magnific), cut out for the game.",
             "If you know a good building pack that is not made with AI, don't hesitate to contact me!"]),
    ("Music", [("Village Medieval Music Pack by Leonardo Calvo (CC BY 4.0) - ",
                "thesoundrack.itch.io/village-medieval-music-pack")]),
    ("Sounds", [("RPG Essentials SFX by Leohpaz - ", "leohpaz.itch.io/rpg-essentials-sfx-free"),
                ("Button click: UI Audio by Kenney - ", "kenney.nl/assets/ui-audio"),
                "The dice sound is made by the game's own code"]),
    ("Font", [("Browser version: Inter by The Inter Project Authors (SIL Open Font License) - ", "github.com/rsms/inter")]),
]
LINK = (40, 90, 160)  # color of clickable links
STOCK_H = 104  # height of the resources box beside the building tree
UNLOCK_TIME = 4.0  # seconds an "Achievement unlocked" message stays

def open_link(url):
    """Open a web page in the player's browser (a new tab in the web version)."""
    try:
        if WEB:
            from platform import window
            window.open(url, "_blank")
        else:
            import webbrowser
            webbrowser.open(url)
    except Exception:
        pass  # no browser: nothing happens


DEMO = False  # the free demo hides the advanced game (see the demo folder)

SEAT_CHOICES = [
    ("Human", "Human", ("Human", "A person plays this seat.")),
    ("Standard AI", "AI", ("Standard AI", "The trained computer: it follows its rules.")),
    ("Advanced AI", "Hard AI", ("Advanced AI", "Before each pawn, it tries every move on possible futures and keeps "
                                       "the one worth the most VP after the next turn's buildings. It thinks "
                                       "a little longer.")),
]


class App:
    """The whole program on screen: the menu, the board, every window, and the link between clicks and the game
    rules."""
    def __init__(self, surface, native=None):
        """Set up the window, the menu choices and everything the screens remember between frames."""
        self.window = surface
        self.native = native    # a pygame.Window, for a sharp picture on Retina screens
        self.fullscreen = True
        self.fonts = {}
        self.words = {}         # text already written at the current size
        self.fit(surface.get_size())
        self.trained = ai.load_trained()
        self.state = "menu"
        self.seats = ["Human", "AI", "AI", "AI"]
        self.player_count = 2
        self.page = "start"
        self.factions_on = False
        self.seat_factions = [None, None, None, None]
        self.names = [""] * 4   # names typed for human players
        self.editing = None     # the seat whose name is being typed
        self.end_time = 0.0     # seconds since the game ended
        self.turn_choices = [8, 12]
        self.turns = 12
        self.advanced = False
        self.mob_abilities = False  # monsters use their abilities in an advanced game
        self.challenge = set()      # advanced game: "weak" (-1 in every fight) and/or "poor" (start with nothing)
        self.event_count = 0   # how many zones get an event in an advanced game (0 = none)
        self.printed = 0       # game log lines already written in the terminal
        self.swap = None  # what the pawn-dismissal window is for
        self.game = None
        self.tutorial = None   # the tutorial, while it runs
        self.confirm_exit = False  # "Exit game" asks before closing
        self.sounds = sound.Sounds()
        self.settings = settings.load()
        self.settings["colorblind"] = False  # the colorblind help starts off each time the game opens
        self.music_volume = self.settings["music"]
        self.sounds.volume = self.settings["sounds"]
        self.achievements = achievements.Tracker()
        self.unlocks = []  # achievements just unlocked, shown one after the other: [key, name, time shown]
        self.walking = []  # where the pawns walking in this frame are going
        self.walked = []   # the same, for the frame before
        self.step_timer = 0.0
        self.heard = None  # the game as the sounds last saw it
        self.button_rects = {}  # where each button was drawn, by label
        self.modal = None
        self.selected = None
        self.lots = {}
        self.hot = []
        self.tips = []
        self.mouse = (0, 0)
        self.ai_timer = 0.0
        self.report_time = 0.0
        self.report_key = None
        self.clock_time = 0.0
        self.view = (0, 0, 1.0)
        self.ai_delay = 0.8
        self.banners = []
        self.banner_time = 0.0
        self.banner_delay = 1.4
        self.toast = ""
        self.toast_time = 0.0
        self.back_to = None
        self.frame_dt = 0.0
        self.pawn_xy = {}
        self.seen = None
        self.report_delay = 1.8
        self.quick_delay = 1.0

    # ---- drawing helpers ----------------------------------------------------
    def font(self, size, bold=False):
        """A font of this size, loaded once and remembered."""
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = load_font(size, bold)
        return self.fonts[key]

    def text(self, value, pos, size=15, color=INK, bold=False, anchor="topleft"):
        """Laid out on the canvas, and written at full screen resolution."""
        value = str(value)
        rect = pygame.Rect((0, 0), self.font(size, bold).size(value))
        setattr(rect, anchor, pos)
        scale = self.canvas.scale
        key = (value, size, bold, tuple(color))
        if key not in self.words:
            if len(self.words) > 3000:
                self.words.clear()
            self.words[key] = self.font(round(size * scale), bold).render(value, True, color)
        image = self.words[key]
        spot = image.get_rect(**{anchor: self.canvas.point(pos)})
        pygame.Surface.blit(self.canvas, image, spot)
        return rect

    def wrap(self, value, width, size=14, bold=False):
        """Split a text into lines that fit width pixels."""
        font = self.font(size, bold)
        lines, line = [], ""
        for word in str(value).split():
            attempt = f"{line} {word}".strip()
            if font.size(attempt)[0] <= width:
                line = attempt
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def para(self, value, x, y, width, size=14, color=INK, bold=False, gap=3):
        """Draw a wrapped paragraph; returns the y just below it."""
        for line in self.wrap(value, width, size, bold):
            self.text(line, (x, y), size, color, bold)
            y += self.font(size, bold).get_height() + gap
        return y

    def click_zone(self, rect, action, tip=None):
        """Make a rectangle clickable this frame, with an optional tooltip."""
        self.hot.append((pygame.Rect(rect), action))
        if tip:
            self.tips.append((pygame.Rect(rect), tip))

    def button(self, rect, label, action, enabled=True, primary=False, size=15, tip=None, icon=None):
        """Draw a button and make it clickable this frame. Its rectangle is remembered by label (for the tutorial
        and tests)."""
        rect = pygame.Rect(rect)
        hover = rect.collidepoint(self.mouse) and enabled
        style = "button_off" if not enabled else "button_red" if primary else "button"
        face = art.button_face(style, rect.w, rect.h)
        ink = MUTED if not enabled else CREAM if primary else INK
        if face:
            if hover:
                face = art.hover_face(style, rect.w, rect.h)
            self.canvas.blit(face, rect)
        else:
            draw.rect(self.canvas, CREAM if hover else PAPER, rect, border_radius=8)
            draw.rect(self.canvas, TABLE_DARK, rect, 2, border_radius=8)
        center = rect.center
        image = art.ui_icon(icon, rect.h - 12) if icon else None
        if image:
            width = self.font(size, True).size(str(label))[0]
            self.canvas.blit(image, (rect.centerx - width // 2 - image.get_width() - 1, rect.y + 5))
            center = (rect.centerx + image.get_width() // 2 - 2, rect.centery)
        self.text(label, (center[0], center[1] - 1), size, ink, True, "center")
        if enabled:
            self.hot.append((rect, action))
        if tip:
            self.tips.append((rect, tip))
        self.button_rects[str(label)] = rect

    def panel(self, rect, color=PAPER, border=TABLE_DARK, radius=10):
        """A paper panel with a dark border."""
        rect = pygame.Rect(rect)
        sheet = art.paper(rect.w, rect.h) if color in (PAPER, CREAM) else None
        if sheet:
            if rect.w >= 560 and rect.h >= 300:
                outer = rect.inflate(24, 24)
                frame = art.wood_frame(outer.w, outer.h)
                if frame:
                    self.canvas.blit(frame, outer)
            self.canvas.blit(sheet, rect)
            return
        draw.rect(self.canvas, color, rect, border_radius=radius)
        draw.rect(self.canvas, border, rect, 2, border_radius=radius)

    def draw_unit(self, kind, team, anim, index, x, y, height, flip=False, gray=False):
        """Draw one animation frame with the feet at (x, y). Returns its rectangle."""
        frame = art.unit_frame(kind, team, anim, index, height, flip, gray)
        if frame:
            image, foot_x, foot_y = frame
            rect = image.get_rect(topleft=(x - foot_x, y - foot_y))
            self.canvas.blit(image, rect)
            return rect
        team_colors = {n.lower(): c for n, c in D.PLAYER_COLORS}
        image = art.pawn(kind if kind in D.PAWNS else "peasant", team_colors.get(team, MUTED), height)
        rect = image.get_rect(midbottom=(x, y))
        self.canvas.blit(image, rect)
        return rect

    def ring(self, x, y, color, width=34, team=None):
        """A colored shape under a character, showing its owner: Red a circle, Blue a square, Yellow a
        triangle, Purple a hexagon, so players can be told apart without the colors."""
        shape = SHAPES.get(team, "circle")
        y -= 5  # centered on the pawn's feet, not under them
        if shape == "circle":
            draw.ellipse(self.canvas, color, (x - width // 2, y - 6, width, 12), 3)
            return
        half, depth = width // 2, 6
        if shape == "square":
            points = [(x - half + 2, y - depth), (x + half - 2, y - depth), (x + half - 2, y + depth),
                      (x - half + 2, y + depth)]
        elif shape == "triangle":
            points = [(x, y - depth - 4), (x + half + 1, y + depth - 1), (x - half - 1, y + depth - 1)]
        else:  # hexagon
            points = [(x - half, y), (x - half // 2, y - depth), (x + half // 2, y - depth), (x + half, y),
                      (x + half // 2, y + depth), (x - half // 2, y + depth)]
        draw.lines(self.canvas, color, True, points, 3)
        for point in points:  # rounded corners, without gaps
            draw.circle(self.canvas, color, point, 1.5)

    def player_mark(self, team, x, y, size, color, outline=None):
        """A player's shape, filled, centered on (x, y): next to names and fight bonuses."""
        shape = SHAPES.get(team, "circle")
        r = size / 2
        if shape == "circle":
            if outline:
                draw.circle(self.canvas, outline, (x, y), r + 1.5)
            draw.circle(self.canvas, color, (x, y), r)
            return
        if shape == "square":
            r *= 0.88
            points = [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)]
        elif shape == "triangle":
            points = [(x, y - r * 1.1), (x + r * 1.1, y + r * 0.85), (x - r * 1.1, y + r * 0.85)]
        else:
            points = [(x + r * math.cos(a * math.pi / 3), y + r * math.sin(a * math.pi / 3)) for a in range(6)]
        if outline:
            draw.polygon(self.canvas, outline, points, 3)
        draw.polygon(self.canvas, color, points)

    def player_name(self, player, text, pos, size, color, bold=True, anchor="midleft"):
        """A player's name in their color; with the colorblind help on, their shape stands in front of it."""
        x, y = pos
        if self.settings["colorblind"]:
            mark = round(size * 0.8)
            line_y = y if anchor.startswith("mid") else y + self.font(size, bold).get_height() // 2
            self.player_mark(player.team, x + mark // 2, line_y, mark, color, TABLE_DARK)
            x += mark + 6
        self.text(text, (x, y), size, color, bold, anchor)

    def res_cost(self, cost, x, y, have=None, size=20):
        """Draw a cost as icons and numbers, in red what the player can't pay."""
        for r, n in cost.items():
            self.canvas.blit(art.resource_icon(r, size), (x, y))
            x += size + 2
            short = have is not None and have.get(r, 0) < n
            rect = self.text(n, (x, y + size // 2), 15, BAD if short else INK, True, "midleft")
            x = rect.right + 8
        return x

    # ---- main loop hooks ----------------------------------------------------
    def click(self, pos):
        """A mouse click: the tutorial gets it first, then the topmost clickable rectangle under the mouse."""
        self.editing = None
        if self.tutorial and self.state == "game" and not self.confirm_exit:
            if self.tutorial.click(pos):
                return True
            if not self.tutorial.allows(pos):
                return False
        for rect, action in reversed(self.hot):
            if rect.collidepoint(pos):
                self.sounds.play("click")
                action()
                return True
        return False

    def footsteps(self):
        """One footstep after another while pawns walk, on the ground of where they go."""
        if not self.walked or not self.game:
            self.step_timer = 0.0
            return
        self.step_timer -= self.frame_dt
        if self.step_timer <= 0:
            self.sounds.play(sound.STEPS.get(self.walked[0], "step_grass"))
            self.step_timer = 0.26

    def listen(self):
        """Play a sound for each change in the game since the last frame."""
        now = sound.snapshot(self.game) if self.game else None
        if now:
            for name, delay in sound.changes(self.heard, now, self.game):
                self.sounds.play(name, delay)
        self.heard = now
        self.footsteps()
        self.sounds.update(self.frame_dt)
        if pygame.mixer.get_init() and not getattr(self, "muted", False):
            level = self.music_volume * self.sounds.music_level()
            current = pygame.mixer.music.get_volume()
            if WEB:  # a browser crackles when the volume changes every frame: change it once
                if abs(current - level) > 0.05:
                    pygame.mixer.music.set_volume(level)
            elif abs(current - level) > 0.01:  # glide, so the music doesn't jump
                step = 1.5 * self.frame_dt
                pygame.mixer.music.set_volume(max(level, current - step) if current > level
                                              else min(level, current + step * 0.5))

    # ---- music --------------------------------------------------------------
    music_volume = 0.5

    def play_music(self, track):
        """Loop assets/music/<track>.ogg, fading from one piece to the next. Silent if sound is off."""
        if track == "game" and self.settings["track"] != "usual":
            track = self.settings["track"]  # the chosen piece plays during the game; the menu keeps its own
        if getattr(self, "music_track", None) == track:
            return
        self.music_track = track
        path = os.path.join(art.ROOT, "music", f"{track}.ogg")
        try:
            if not pygame.mixer.get_init() or not os.path.exists(path):
                return
            pygame.mixer.music.load(path)  # stops the previous piece (fadeout would freeze the game)
            pygame.mixer.music.set_volume(self.music_volume if not getattr(self, "muted", False) else 0)
            pygame.mixer.music.play(-1, fade_ms=1500)
        except pygame.error:
            pass  # no sound card: play on without music

    def toggle_music(self):
        """M turns the music and the sound effects off or on."""
        self.muted = not getattr(self, "muted", False)
        self.sounds.muted = self.muted
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(0 if self.muted else self.music_volume)
        self.toast, self.toast_time = ("Sound off" if self.muted else "Sound on"), 1.6

    # ---- keyboard -----------------------------------------------------------
    def key(self, key, char=""):
        """A key press: Escape closes windows or switches full screen, M mutes, R, B and Z open windows."""
        if self.confirm_exit:
            if key == pygame.K_ESCAPE:
                self.confirm_exit = False
            return
        if self.editing is not None:
            self.type_name(key, char)
        elif key == pygame.K_m and not self.modal:
            self.toggle_music()
        elif self.tutorial and key == pygame.K_ESCAPE and self.modal and self.modal not in VIEWERS:
            return  # the tutorial decides when its windows close
        elif key == pygame.K_ESCAPE and self.modal in VIEWERS:
            self.close_viewer()
        elif key == pygame.K_ESCAPE and self.modal:
            self.modal = None
        elif key == pygame.K_ESCAPE and self.state == "menu" and self.page != "start":
            self.page = {"players": "mode", "mode": "start"}.get(self.page, "start")
        elif key == pygame.K_ESCAPE:
            self.toggle_fullscreen()
        elif key == pygame.K_r and self.state == "game":
            if self.modal == "rules":
                self.close_viewer()
            else:
                self.open_rules()
        elif key == pygame.K_b and self.state == "game":
            self.open_catalog()
        elif key == pygame.K_z and self.state == "game":
            self.open_zones()

    def type_name(self, key, char):
        """Typing in a player's name field."""
        name = self.names[self.editing]
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_TAB):
            self.editing = None
        elif key == pygame.K_BACKSPACE:
            self.names[self.editing] = name[:-1]
        elif char and char.isprintable() and len(name) < MAX_NAME:
            self.names[self.editing] = name + char

    def seat_name(self, i):
        """What this seat is called: typed for a human, numbered for computers."""
        seat = self.seats[i]
        if seat == "Human":
            return self.names[i].strip() or f"Player {i + 1}"
        return f"AI_{sum(s != 'Human' for s in self.seats[:i + 1])}"

    def print_log(self):
        """The story of the game goes to the terminal."""
        logs = self.game.logs if self.game else []
        for line in logs[self.printed:]:
            print(line, flush=True)
        self.printed = len(logs)

    # ---- every frame: the game moves on -------------------------------------
    def update(self, dt):
        """Each frame: music and sounds, then let the game move on (banners, reports, computer players)."""
        self.clock_time += dt
        self.frame_dt = dt
        self.play_music("game" if self.game else "menu")
        self.listen()
        self.print_log()
        if self.modal == "alchemy" and self.game and not any(
                allowed for _, options in self.alchemy_rows() for *_, allowed in options):
            self.modal = None  # nothing left to transform
        if self.modal in VIEWERS:
            return  # the game waits while you read
        self.toast_time = max(0.0, self.toast_time - dt)
        g = self.game
        if self.state != "game" or g is None:
            return
        for key, name in self.achievements.update(g):
            self.unlocks.append([key, name, 0.0])
            self.sounds.play("recruit")
        if self.unlocks:
            self.unlocks[0][2] += dt
            if self.unlocks[0][2] > UNLOCK_TIME:
                self.unlocks.pop(0)
        if self.tutorial:
            self.banners = []  # the guide explains each step instead
            self.tutorial.update(dt)
        if g.phase == "end":
            self.modal = None
            self.end_time += dt
            return
        self.track_phase()
        if self.banners:
            self.banner_time += dt
            if self.banner_time >= self.banner_delay:
                self.banners.pop(0)
                self.banner_time = 0.0
            self.fix_selection()
            return
        key = (g.turn, len(g.harvest_queue), g.harvest_stage)
        if key != self.report_key:
            self.report_key = key
            self.report_time = 0.0
        self.report_time += dt
        if self.modal in ("build", "town", "alchemy", "dismiss", "end_check", "horn") and (g.phase != "actions" or g.players[g.active].is_ai):
            self.modal = None
        if g.phase == "harvest" and g.harvest_stage == "next":
            g.harvest_next()
            return
        if g.phase == "harvest" and g.harvest_stage == "report":
            present = {pid for pid, *_ in g.report["gathers"]}
            if self.no_fight():
                self.quick_summary(present)
                if self.report_time > self.quick_delay:
                    self.acknowledge()
                return
            wait = self.report_delay + (FIGHT_TIME if g.report["rolls"] else 0)
            if all(g.players[pid].is_ai for pid in present) and self.report_time > wait:
                self.acknowledge()
            return
        if g.players[g.active].is_ai and not self.tutorial:
            self.ai_timer += dt
            if self.ai_timer >= self.ai_delay:
                self.ai_timer = 0
                before = len(g.logs)
                ai.play_step(g)
                if len(g.logs) > before:
                    self.toast = g.logs[before]
                    self.toast_time = 1.6
        self.fix_selection()

    def track_phase(self):
        """Announce each step, including steps that nobody can act in."""
        g = self.game
        now = (g.turn, g.phase)
        old = self.seen
        self.seen = now
        if old is None or old == now:
            return
        new_turn = g.turn != old[0]
        if old[1] == "deploy":
            if g.phase == "actions":
                self.banners.append("Step 2: Build and trade")
            else:
                self.banners.append("Step 2: no pawn at home or in town")
        if g.phase == "harvest":
            self.banners.append("Step 3: Harvest and fight")
        elif new_turn and old[1] != "harvest":
            self.banners.append("Step 3: no pawn in the environments")
        if new_turn:
            self.banners.append(f"Turn {g.turn}: new resources and prices")

    def no_fight(self):
        """True when one player was alone there and nothing needed a fight."""
        g = self.game
        report = g.report
        owners = {pid for pid, *_ in report["gathers"]}
        return (g.harvest_stage == "report" and len(owners) == 1 and not report["rolls"]
                and not report.get("notes") and not report.get("event_dice"))

    def quick_summary(self, present):
        """Show what a lone player collected, without a window."""
        g = self.game
        report = g.report
        pid = next(iter(present))
        totals = {}
        for _, res, qty, _ in report["gathers"]:
            totals[res] = totals.get(res, 0) + qty
        for _, res, qty in report["awards"]:
            totals[res] = totals.get(res, 0) + qty
        items = ", ".join(f"+{qty} {res_name(res)}" for res, qty in totals.items())
        self.toast = f"{g.players[pid].name} at {g.env(report['env']).name}: {items}"
        self.toast_time = 0.3

    def acknowledge(self):
        """Close the current harvest report."""
        if self.game.harvest_stage == "report":
            self.game.ack_report()

    def fix_selection(self):
        """Keep a valid pawn selected while a human sends pawns."""
        g = self.game
        if g.phase != "deploy" or g.players[g.active].is_ai:
            self.selected = None
            return
        pawns = g.deployable(g.active)
        if pawns and self.selected not in [x.uid for x in pawns]:
            self.selected = pawns[0].uid

    # ---- menu ---------------------------------------------------------------
    def start_game(self):
        """Build the game from the menu choices (players, turns, events, factions) and show the board."""
        roster = []
        for i, seat in enumerate(self.seats[:self.player_count]):
            roster.append((self.seat_name(i), seat != "Human", i))
        seed = random.randrange(10 ** 9)
        events = self.event_count if self.advanced else False  # 0 events: no event at all
        factions = self.pick_factions() if self.advanced and self.factions_on else None
        self.game = Game([(n, a) for n, a, _ in roster], turns=self.turns, seed=seed, events=events,
                         factions=factions, mob_abilities=self.advanced and self.mob_abilities,
                         challenge=self.challenge if self.advanced else ())
        self.printed = 0
        for player, (_, _, slot) in zip(self.game.players, roster):
            player.color = D.PLAYER_COLORS[slot][1]
            player.team = D.PLAYER_COLORS[slot][0].lower()
            if self.seats[slot] in ("AI", "Hard AI"):
                kind = (self.turns, len(roster), self.advanced and self.event_count > 0)
                brain = ai.load_for(*kind)
                self.game.brains[player.pid] = ai.hard_brain(brain, game_type=kind) if self.seats[slot] == "Hard AI" else brain
        self.state = "game"
        self.editing = None
        self.end_time = 0.0
        self.modal = "zones" if self.advanced and self.event_count else None  # show this game's events first
        self.back_to = None
        self.banners = ["Turn 1: new resources and prices"]
        self.banner_time = 0.0
        self.seen = None
        self.pawn_xy = {}
        self.fix_selection()

    def start_tutorial(self):
        """Start Sir Pebble's tutorial game."""
        import tutorial
        self.tutorial = tutorial.Tutorial(self)
        self.game = self.tutorial.game
        self.state = "game"
        self.editing = None
        self.modal = None
        self.back_to = None
        self.banners = []
        self.printed = 0
        self.seen = None
        self.pawn_xy = {}
        self.fix_selection()

    def draw_menu(self):
        """The start screen: the animated picture and the menu pages."""
        c = self.canvas
        ground = art.menu_ground(W, H) if art.menu_actors() else None
        picture = ground or art.menu_picture(W, H)
        if ground:  # the picture comes alive: its people, sheep and trees move
            c.blit_opaque(ground, (0, 0))
            k = W / 2560
            for a in art.menu_actors():
                index = (int(self.clock_time * a["fps"]) + a["start"]) % a["frames"]
                sheet, x = a["sheet"], a["x"]
                if a.get("hit"):  # still, until the stone lands
                    h = a["hit"]
                    since = (self.clock_time - h["t_hit"]) % h["period"]
                    index = 1 + int(since * h["fps"]) if since * h["fps"] < a["frames"] - 1 else 0
                if a.get("fly"):  # a stone in flight, only after the sling lets go
                    f = a["fly"]
                    t = (self.clock_time % f["period"] - f["t0"]) / f["dur"]
                    if not 0 <= t <= 1:
                        continue
                    cx = f["x0"] + (f["x1"] - f["x0"]) * t
                    cy = f["y0"] + (f["y1"] - f["y0"]) * t - f["arc"] * 4 * t * (1 - t)
                    image = art.menu_frame(sheet, a["frames"], index, round(a["w"] * k), round(a["h"] * k))
                    if image and "aim" in f:  # an arrow points where it flies: up, then down
                        vx = f["x1"] - f["x0"]
                        vy = f["y1"] - f["y0"] - f["arc"] * 4 * (1 - 2 * t)
                        image = pygame.transform.rotate(image, math.degrees(math.atan2(-vy, vx)) - f["aim"])
                    if image:
                        w, h = image.get_size()
                        c.blit(image, (round(cx * k - w / 2), round(cy * k - h / 2)))
                    continue
                if a.get("walk"):  # back and forth along a short path
                    trip = (self.clock_time * a["speed"] / a["walk"]) % 2
                    shift = a["dir"] * a["walk"] * (trip if trip < 1 else 2 - trip)
                    sheet, x = (sheet, x + shift) if trip < 1 else (a["back"], a["back_x"] + shift)
                if a.get("sway"):  # steps forward and back while fighting
                    x += a["sway"] * math.sin(self.clock_time * 2 * math.pi / a["sway_period"])
                image = art.menu_frame(sheet, a["frames"], index, round(a["w"] * k), round(a["h"] * k))
                if image:
                    c.blit(image, (round(x * k), round(a["y"] * k)))
        elif picture:
            c.blit(picture, (0, 0))  # the title is written in the picture
        else:
            c.fill(TABLE)
            self.text("Tiny Realms", (W // 2, 92), 62, ACCENT_LIGHT, True, "center")
        if self.page == "start":
            self.button((W // 2 - 140, 470, 280, 64), "Start", lambda: setattr(self, "page", "mode"),
                        primary=True, size=26)
            self.button((W // 2 - 110, 548, 220, 48), "Achievements", lambda: setattr(self, "page", "achievements"),
                        size=20)
            self.button((W // 2 - 110, 604, 220, 48), "Settings", lambda: setattr(self, "page", "settings"), size=20)
            self.button((W // 2 - 110, 660, 220, 48), "Credits", lambda: setattr(self, "page", "credits"), size=20)
            if not WEB:  # a web page can't close itself
                self.button((W // 2 - 110, 716, 220, 48), "Exit game", self.quit_game, size=20)
        elif self.page == "achievements":
            self.draw_achievements_page()
        elif self.page == "credits":
            self.draw_credits_page()
        elif self.page == "settings":
            self.draw_settings(lambda: setattr(self, "page", "start"))
        elif self.page == "mode":
            self.draw_mode_page()
        else:
            self.draw_players_page()

    @staticmethod
    def quit_game():
        """Close the window, like Cmd+Q."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def draw_mode_page(self):
        """Page 2 of the menu: normal or advanced game, number of turns and events."""
        box = pygame.Rect(W // 2 - 300, 150, 600, 530 if self.advanced else 400)
        self.panel(box)
        self.text("Choose a game", (box.centerx, box.y + 32), 24, INK, True, "center")
        self.button((box.x + 40, box.y + 64, 250, 56), "Normal game", lambda: setattr(self, "advanced", False),
                    primary=not self.advanced, size=18)
        self.button((box.right - 290, box.y + 64, 250, 56), "Advanced game", lambda: setattr(self, "advanced", True),
                    primary=self.advanced, size=18)
        y = box.y + 150
        self.text("Turns", (box.x + 40, y + 20), 18, INK, True, "midleft")
        for i, t in enumerate(self.turn_choices):
            self.button((box.x + 200 + i * 80, y, 70, 40), t, lambda t=t: setattr(self, "turns", t),
                        primary=t == self.turns)
        if self.advanced:
            y += 60
            most = D.zone_count(self.player_count) + 1  # and the Market
            self.event_count = min(self.event_count, most)
            tip = ("Events", f"Each event is a special rule placed on a random zone or on the Market, for the "
                             f"whole game: some help (Good Fishing, Sunken Treasure), some hurt (Avalanche, Swamp "
                             f"Gas). More events, more surprises. You choose how many: 0 to {most}. During the "
                             f"game, a red tag on a zone shows its event.")
            self.text("Events", (box.x + 40, y + 20), 18, INK, True, "midleft")
            self.tips.append((pygame.Rect(box.x + 30, y, 160, 40), tip))  # hover the word too
            self.button((box.x + 200, y + 2, 36, 36), "-", lambda: self.change_events(-1), self.event_count > 0, tip=tip)
            self.text(self.event_count, (box.x + 263, y + 20), 20, INK, True, "center")
            self.button((box.x + 290, y + 2, 36, 36), "+", lambda: self.change_events(1), self.event_count < most, tip=tip)
            self.text(f"0 to {most}", (box.x + 342, y + 20), 14, MUTED, False, "midleft")
            y += 60
            self.text("Factions", (box.x + 40, y + 20), 18, INK, True, "midleft")
            tip = ("Factions", "Each player starts with their faction's pawns instead of 2 Peasants.")
            self.tips.append((pygame.Rect(box.x + 30, y, 160, 40), tip))
            for i, (label, value) in enumerate((("Off", False), ("On", True))):
                self.button((box.x + 200 + i * 80, y, 70, 40), label, lambda v=value: setattr(self, "factions_on", v),
                            primary=value == self.factions_on, tip=tip)
            y += 60
            self.text("Monster abilities", (box.x + 40, y + 20), 18, INK, True, "midleft")
            tip = ("Monster abilities", "Gnolls take gold, Bears and Skeletons give a resource, Snakes wound "
                                        "and Spiders trap a pawn. See the Zones window.")
            self.tips.append((pygame.Rect(box.x + 30, y, 165, 40), tip))
            for i, (label, value) in enumerate((("Off", False), ("On", True))):
                self.button((box.x + 200 + i * 80, y, 70, 40), label, lambda v=value: setattr(self, "mob_abilities", v),
                            primary=value == self.mob_abilities, tip=tip)
            y += 60
            self.text("Challenge", (box.x + 40, y + 20), 18, INK, True, "midleft")
            tip = ("Challenge", "Harder rules for the human players only: the computers play normally, so they "
                                "are harder to beat. Choose one, both or none.")
            self.tips.append((pygame.Rect(box.x + 30, y, 160, 40), tip))
            options = (("weak", "-1 in fights", "Human players have -1 in every fight. The computers don't."),
                       ("poor", "Start with nothing", "Human players start with no gold and no resources. The "
                                                      "computers start normally."))
            x = box.x + 200
            for key, label, text in options:
                width = self.font(15, False).size(label)[0] + 30
                self.button((x, y, width, 40), label, lambda k=key: self.toggle_challenge(k),
                            primary=key in self.challenge, tip=("Challenge: " + label, text))
                x += width + 10
        self.button((box.x + 40, box.bottom - 64, 160, 44), "Back", lambda: setattr(self, "page", "start"), size=16)
        self.button((box.centerx - 70, box.bottom - 64, 140, 44), "Tutorial", self.start_tutorial, size=16,
                    tip=("Tutorial", "New to Tiny Realms? Learn to play in one guided turn."))
        self.button((box.right - 200, box.bottom - 64, 160, 44), "Next", lambda: setattr(self, "page", "players"),
                    primary=True, size=16)

    def draw_players_page(self):
        """Page 3 of the menu: the players, human or AI, their names and factions."""
        factions = self.advanced and self.factions_on
        box = pygame.Rect(W // 2 - (360 if factions else 280), 136 if factions else 170, 720 if factions else 560,
                          396 if factions else 470)
        self.panel(box)
        self.text("Players", (box.x + 28, box.y + 22), 22, INK, True)
        for n in (2, 3, 4):
            self.button((box.right - 290 + (n - 2) * 86, box.y + 16, 78, 38), f"{n} players",
                        lambda n=n: self.set_player_count(n), primary=n == self.player_count, size=14)
        for i in range(self.player_count):
            y = box.y + 70 + i * 62
            team = D.PLAYER_COLORS[i][0].lower()
            self.draw_unit("peasant", team, art.IDLE, int(self.clock_time * 8) + i * 2, box.x + 48, y + 40, 38)
            self.draw_name_field(i, pygame.Rect(box.x + 80, y + 6, 160, 38))
            x = box.x + 250
            for k, (label, value, tip) in enumerate(SEAT_CHOICES):
                width = (70, 96, 100)[k]
                self.button((x, y + 3, width, 44), label, lambda i=i, v=value: self.set_seat(i, v),
                            primary=self.seats[i] == value, size=13)
                x += width + 4
            if factions:
                choice = self.seat_factions[i]
                label = D.FACTIONS[choice]["name"] if choice else "Random faction"
                pawns = ", ".join(D.PAWNS[k]["name"] for k in D.FACTIONS[choice]["pawns"]) if choice else ""
                level = D.FACTIONS[choice]["difficulty"] if choice else 0
                hint = f" Difficulty: {D.DIFFICULTY_NAMES[level]} ({level}/5)." if level else ""
                self.button((box.x + 532, y + 3, 168, 44), label, lambda i=i: self.cycle_faction(i), size=13,
                            tip=(label, f"Starting pawns: {pawns}.{hint}" if pawns else "A faction no one else has."))
        self.button((box.x + 28, box.bottom - 64, 160, 44), "Back", lambda: setattr(self, "page", "mode"), size=16)
        self.button((box.right - 288, box.bottom - 64, 260, 44), "Start game", self.start_game, primary=True,
                    size=18)
        if factions:
            self.draw_faction_cards(box.bottom + 8)

    def draw_faction_cards(self, top):
        """What each faction's starting pawns do, to help choose."""
        width = (W - 40 - 30) // 4
        for k, (key, info) in enumerate(D.FACTIONS.items()):
            card = pygame.Rect(20 + k * (width + 10), top, width, H - top - 10)
            self.panel(card)
            self.text(info["name"], (card.centerx, card.y + 18), 16, ACCENT, True, "center")
            level = info["difficulty"]
            label = f"{D.DIFFICULTY_NAMES[level]} ({level}/5)"
            label_w = self.font(12, True).size(label)[0]
            left = card.centerx - (label_w + 8 + 5 * 15) // 2
            self.text(label, (left, card.y + 30), 12, MUTED, True)
            self.draw_stars(left + label_w + 8, card.y + 38, level)
            y = card.y + 52
            for i, kind in enumerate(info["pawns"]):
                pawn = D.PAWNS[kind]
                self.draw_unit(kind, "all", art.IDLE, int(self.clock_time * 8) + i * 3, card.x + 30, y + 42, 30)
                self.text(pawn["name"], (card.x + 62, y + 4), 13, INK, True)
                self.text(f"{D.pawn_vp(kind)} VP", (card.right - 12, y + 4), 12, ACCENT, True, "topright")
                ability = pawn["desc"].replace("Starting pawn. ", "")
                lines = self.wrap(ability, width - 70, 11)  # every line: long abilities push the next pawn down
                for j, line in enumerate(lines):
                    self.text(line, (card.x + 62, y + 21 + j * 13), 11, MUTED)
                y += max(66, 21 + len(lines) * 13 + 10)

    def draw_stars(self, x, y, filled, total=5, size=7):
        """A row of small stars, the first ones filled (the faction's difficulty)."""
        for i in range(total):
            cx = x + i * (size * 2 + 1) + size
            points = [(cx + (size if k % 2 == 0 else size * 0.45) * math.sin(k * math.pi / 5),
                       y - (size if k % 2 == 0 else size * 0.45) * math.cos(k * math.pi / 5)) for k in range(10)]
            if i < filled:
                draw.polygon(self.canvas, ACCENT, points)
            draw.polygon(self.canvas, ACCENT if i < filled else MUTED, points, 1)

    def set_player_count(self, n):
        """Choose how many players there are."""
        self.player_count = n
        if self.editing is not None and self.editing >= n:
            self.editing = None

    def set_seat(self, i, value):
        """Make a player human or computer."""
        self.seats[i] = value
        if value != "Human" and self.editing == i:
            self.editing = None

    def cycle_faction(self, i):
        """Click on a player's faction: the next one (or none)."""
        order = [None] + list(D.FACTIONS)
        self.seat_factions[i] = order[(order.index(self.seat_factions[i]) + 1) % len(order)]

    def pick_factions(self):
        """Chosen factions stay; random seats get one nobody chose, when there is one left."""
        chosen = list(self.seat_factions[:self.player_count])
        free = [f for f in D.FACTIONS if f not in chosen]
        random.shuffle(free)
        for i, f in enumerate(chosen):
            if f is None:
                chosen[i] = free.pop() if free else random.choice(list(D.FACTIONS))
        return chosen

    def toggle_challenge(self, key):
        """Turn one challenge rule on or off."""
        self.challenge ^= {key}

    def change_events(self, delta):
        """One more or one less zone event."""
        self.event_count += delta

    def draw_name_field(self, i, rect):
        """A box to type a human's name in. Computers keep their numbered name."""
        c = self.canvas
        seat = self.seats[i]
        if seat != "Human":
            label = "" if seat == "Off" else self.seat_name(i)
            self.text(label or "Off", (rect.x + 8, rect.centery), 16, MUTED if seat == "Off" else INK, seat != "Off", "midleft")
            return
        editing = self.editing == i
        draw.rect(c, CREAM, rect, border_radius=6)
        draw.rect(c, ACCENT if editing else MUTED, rect, 2 if editing else 1, border_radius=6)
        typed = self.names[i]
        label = typed if typed or editing else self.seat_name(i)
        self.text(label, (rect.x + 8, rect.centery), 16, INK if typed else MUTED, bool(typed), "midleft")
        if editing and int(self.clock_time * 2) % 2 == 0:
            x = rect.x + 9 + self.font(16, bool(typed)).size(label)[0]
            draw.line(c, INK, (x, rect.y + 8), (x, rect.bottom - 8), 2)
        self.click_zone(rect, lambda: setattr(self, "editing", i),
                        ("Player name", "Click and type a name, then press Enter."))

    # ---- players' panels and realms -----------------------------------------
    def base_rects(self):
        """Place bases on the left and right edges, centred if alone on a side."""
        n = len(self.game.players)
        left = (0 + 1) if n == 2 else (n + 1) // 2
        rects = []
        height = (H - TOP_H - 12) // 2
        for i in range(n):
            on_left = i < left
            count = left if on_left else n - left
            slot = i if on_left else i - left
            x = 6 if on_left else W - SIDE_W + 6 - 12
            y = (TOP_H + 8 + slot * (height + 2)) if count == 2 else (TOP_H + 8 + height // 2)
            rects.append(pygame.Rect(x, y, SIDE_W, height - 4))
        return rects

    def walk_position(self, uid, x, y):
        """Move a character smoothly towards its place. Returns (x, y, walking, facing left)."""
        now = self.pawn_xy.setdefault(uid, [x, y])
        dx, dy = x - now[0], y - now[1]
        distance = (dx * dx + dy * dy) ** 0.5
        step = 340 * self.frame_dt
        if distance <= max(step, 2):
            now[0], now[1] = x, y
            return x, y, False, False
        now[0] += dx / distance * step
        now[1] += dy / distance * step
        return int(now[0]), int(now[1]), True, dx < 0

    def draw_pawn(self, pawn, x, y, height=40, ring=34):
        """Draw an animated character with its feet at (x, y)."""
        g = self.game
        owner = g.players[pawn.owner]
        px, py, walking, left = self.walk_position(pawn.uid, x, y)
        if walking:
            self.walking.append(pawn.location)  # footsteps play while someone walks
        anim = art.RUN if walking else art.IDLE
        index = int(self.clock_time * (12 if walking else 8)) + pawn.uid * 3
        chosen = pawn.uid == self.selected  # the chosen pawn's shape turns yellow
        self.ring(px, py, (255, 240, 120) if chosen else owner.color, ring, owner.team)
        rect = self.draw_unit(pawn.kind, owner.team, anim, index, px, py, height, left, pawn.resting)
        click = rect.inflate(-4, -10)
        if pawn.leaving:
            top = py - 40
            for a, b in (((px - 4, top - 4), (px + 4, top + 4)), ((px - 4, top + 4), (px + 4, top - 4))):
                draw.line(self.canvas, BAD, a, b, 3)
            status = " Leaves at the start of next turn, and no longer counts for VP."
        elif pawn.webbed and pawn.location != HOME:
            status = " Caught in a web: stays in this zone this turn."
        elif pawn.stuck and pawn.resting:
            status = " Left behind: misses this turn."
        elif pawn.resting:
            status = " Wounded: misses this turn."
        elif pawn.used:
            status = " Has acted this turn."
        elif pawn.placed and pawn.location == HOME:
            status = " Staying home this turn."
        else:
            status = ""
        tip = (f"{pawn.name} ({self.game.players[pawn.owner].name})",
               f"{pawn.info['desc']} {self.game.pawn_points(pawn)} VP.{status}")
        self.tips.append((click, tip))
        return click

    def draw_base(self, player, rect):
        """A player's side panel: name, VP, gold, resources, realm and the pawns at home."""
        c = self.canvas
        g = self.game
        waiting_on = g.phase in ("deploy", "actions") or g.harvest_stage in ("stance", "choice")
        is_active = waiting_on and g.active == player.pid
        if is_active:  # the panel itself is in the board's picture
            draw.rect(c, ACCENT_LIGHT, rect, 4, border_radius=10)
        head = pygame.Rect(rect.x + 4, rect.y + 5, rect.w - 8, 34)
        self.player_mark(player.team, head.x + 40, head.centery, 12, CREAM)
        self.text(player.name, (head.x + 52, head.centery), 14, CREAM, True, "midleft")
        c.blit(art.resource_icon("gold", 22), (head.right - 72, head.y + 5))
        self.text(player.gold, (head.right - 49, head.centery), 17, CREAM, True, "midleft")
        income = player.building_sum("gold_per_turn")
        if income:
            self.income_badge(head.right - 66, head.y + 1, income)
            self.tips.append((pygame.Rect(head.right - 72, head.y, 50, head.h),
                              ("Gold", f"+{income} gold each turn from {player.name}'s buildings.")))
        buildings, pawns = g.victory_points(player.pid)[:2]
        self.text(f"{buildings + pawns} VP", (head.right - 78, head.centery), 15, CREAM, True, "midright")
        self.tips.append((pygame.Rect(head.right - 130, head.y, 52, head.h),
                          ("Victory points", "From buildings and pawns. At the end of the game, every 5 gold "
                                             "(unsold resources count too) adds 1 VP more.")))

        x0, y0 = rect.x + 12, rect.y + 41
        for i, r in enumerate(D.RESOURCE_IDS):
            x = x0 + (i % 5) * 56
            y = y0 + (i // 5) * 25
            n = player.res[r]
            c.blit(art.resource_icon(r, 21) if n else art.faded_icon(r, 21), (x, y))
            self.text(n, (x + 25, y + 11), 15, INK if n else MUTED, n > 0, "midleft")
            made = sum(D.BUILDINGS[b].get("produce", {}).get(r, 0) for b in player.buildings)
            if made:
                self.income_badge(x + 9, y - 5, made)
                givers = ", ".join(D.BUILDINGS[b]["name"] for b in player.buildings
                                   if r in D.BUILDINGS[b].get("produce", {}))
                tip = (D.RESOURCES[r][0], f"+{made} {D.RESOURCES[r][0]} each turn, from: {givers}.")
            else:
                tip = (D.RESOURCES[r][0], "")
            self.tips.append((pygame.Rect(x, y, 48, 22), tip))

        plot = self.plot_rect(rect)
        self.plot_tips(player, plot)
        if g.first == player.pid:
            flag = pygame.Rect(plot.x + 6, plot.y + 6, 88, 20)
            draw.rect(c, TABLE_DARK, flag, border_radius=6)
            self.text("First player", flag.center, 12, CREAM, True, "center")
        if is_active:
            self.draw_turn_icon(plot.right - 56, plot.y + 40, player.team)
        self.draw_pawn_count(player, plot)
        self.draw_building_count(player, plot)

        home = [x for x in player.pawns if x.location == HOME]
        strip = pygame.Rect(rect.x + 6, rect.bottom - 52, rect.w - 12, 46)
        self.strip_floor = strip.bottom - 5
        draw.rect(c, PAPER_DARK, strip, border_radius=7)
        if home and g.phase == "deploy":
            self.draw_home_groups(player, strip, home)
        elif home:
            self.draw_home_pawns(home, strip.x + 22, strip.w - 30)
        else:
            self.text("Nobody home", strip.center, 13, MUTED, False, "center")

    def income_badge(self, x, y, n):
        """A little green +n: what a building gives each turn."""
        c = self.canvas
        tag = pygame.Rect(x, y, 19, 12)
        draw.rect(c, (48, 120, 60), tag, border_radius=5)
        draw.rect(c, CREAM, tag, 1, border_radius=5)
        self.text(f"+{n}", (tag.centerx, tag.centery), 10, CREAM, True, "center")

    def draw_pawn_count(self, player, plot):
        """How many pawns this player has, out of the most allowed."""
        g = self.game
        count = sum(1 for x in player.pawns if not x.leaving)
        limit = g.pawn_limit(player.pid)
        tag = pygame.Rect(plot.x + 6, plot.bottom - 26, 92, 20)
        draw.rect(self.canvas, TABLE_DARK, tag, border_radius=6)
        self.text(f"Pawns {count}/{limit}", tag.center, 12, BAD_LIGHT if count >= limit else CREAM, True, "center")
        self.tips.append((tag, ("Pawns", f"{player.name} has {count} pawns out of {limit}. With {limit}, a new "
                                         "recruit replaces one of them.")))

    def draw_building_count(self, player, plot):
        """How many buildings this player has, out of the most allowed (the Town Hall is not counted)."""
        count, limit = len(player.buildings), D.MAX_BUILDINGS
        tag = pygame.Rect(plot.right - 118, plot.bottom - 26, 112, 20)
        draw.rect(self.canvas, TABLE_DARK, tag, border_radius=6)
        self.text(f"Buildings {count}/{limit}", tag.center, 12, BAD_LIGHT if count >= limit else CREAM, True, "center")
        self.tips.append((tag, ("Buildings", f"{player.name} has {count} buildings out of {limit}, "
                                             "not counting the Town Hall.")))

    def draw_turn_icon(self, x, y, team):
        """A bouncing knight's face on the board of the player whose turn it is."""
        c = self.canvas
        y += int(3 * math.sin(self.clock_time * 5))
        draw.circle(c, TABLE_DARK, (x, y), 28)
        draw.circle(c, CREAM, (x, y), 26)
        face = art.turn_face(team, 46)
        if face:
            c.blit(face, face.get_rect(center=(x, y)))
        else:
            draw.polygon(c, TABLE_DARK, [(x - 8, y - 12), (x + 13, y), (x - 8, y + 12)])
        tag = pygame.Rect(x - 37, y + 31, 74, 21)
        draw.rect(c, TABLE_DARK, tag, border_radius=6)
        self.text("Playing", tag.center, 13, ACCENT_LIGHT, True, "center")

    def draw_home_pawns(self, pawns, x, width):
        """A row of home pawns. Only the active human's waiting pawns can be clicked."""
        g = self.game
        step = min(36, width // max(1, len(pawns)))
        for i, pawn in enumerate(pawns):
            px = x + i * step
            click = self.draw_pawn(pawn, px, self.strip_floor, min(36, step + 1), min(34, step - 7))
            click = pygame.Rect(px - step // 2, click.y, step, click.h)  # neighbours never overlap
            if pawn.placed and not pawn.resting:
                self.draw_home_badge(px + 11, self.strip_floor - 31)
            if (g.phase == "deploy" and pawn.owner == g.active and not g.players[pawn.owner].is_ai
                    and pawn in g.deployable(pawn.owner)):
                self.click_zone(click, lambda u=pawn.uid: setattr(self, "selected", u))

    def draw_home_groups(self, player, strip, home):
        """While placing: pawns still waiting on the left, pawns staying on the right."""
        waiting = [x for x in home if not x.placed and not x.resting]
        staying = [x for x in home if x.placed or x.resting]
        if not staying or not waiting:
            self.draw_home_pawns(waiting or staying, strip.x + 22, strip.w - 30)
            return
        step = min(36, (strip.w - 44) // len(home))
        split = strip.right - len(staying) * step - 8
        side = pygame.Rect(split, strip.y, strip.right - split, strip.h)
        draw.rect(self.canvas, (222, 201, 160), side,
                         border_top_right_radius=7, border_bottom_right_radius=7)
        draw.line(self.canvas, TABLE_DARK, (split, strip.y + 3), (split, strip.bottom - 4), 2)
        self.draw_home_pawns(waiting, strip.x + 20, len(waiting) * step)
        self.draw_home_pawns(staying, split + 4 + step // 2, len(staying) * step)

    def draw_home_badge(self, x, y):
        """A little house above a pawn that was told to stay home."""
        c = self.canvas
        draw.circle(c, TABLE_DARK, (x, y), 9)
        draw.circle(c, CREAM, (x, y), 8)
        draw.polygon(c, BAD, [(x - 6, y), (x, y - 6), (x + 6, y)])
        draw.rect(c, TABLE_DARK, (x - 4, y, 8, 5))
        draw.rect(c, CREAM, (x - 1, y + 2, 2, 3))

    def draw_plot(self, player, plot):
        """A player's realm: the building grid with the Town Hall in the middle and the buildings around it."""
        c = self.canvas
        ground = art.home_ground(plot.w, plot.h)
        if ground:
            c.blit(ground, plot)
            draw.rect(c, (60, 92, 52), plot, 2, border_radius=7)
        else:
            draw.rect(c, (120, 168, 88), plot, border_radius=7)
        cx = plot.centerx
        tw, th = 66, 33
        grid = 4
        top = plot.bottom - grid * th - 12
        cells = ["hall"] + list(player.buildings)
        order = [(i, j) for s in range(grid * 2 - 1) for i in range(grid) for j in range(grid) if i + j == s]
        slots = sorted(order, key=lambda ij: (max(abs(ij[0] - 1.5), abs(ij[1] - 1.5)), ij))
        chosen = dict(zip(slots, cells))
        for i, j in order:
            sx = cx + (i - j) * tw // 2 + 0
            sy = top + (i + j) * th // 2 + th // 2 + 4
            pts = [(sx, sy - th // 2), (sx + tw // 2, sy), (sx, sy + th // 2), (sx - tw // 2, sy)]
            if not ground:
                draw.polygon(c, (132, 180, 96), pts)
            draw.polygon(c, (78, 118, 62), pts, 1)  # the building grid
        for i, j in order:
            if (i, j) not in chosen:
                continue
            kind = chosen[(i, j)]
            sx = cx + (i - j) * tw // 2
            sy = top + (i + j) * th // 2 + th // 2 + 4
            style = "hall" if kind == "hall" else D.BUILDINGS[kind]["style"]
            small = art.building_at(style, player.color, 68, 79)
            rect = small.get_rect(midbottom=(sx, sy + th // 2 + 2))
            c.blit(small, rect)

    def plot_tips(self, player, plot):
        """What each building in a realm does, when hovered (the buildings are in the board's picture)."""
        tw, th, grid = 66, 33, 4
        top = plot.bottom - grid * th - 12
        cells = ["hall"] + list(player.buildings)
        order = [(i, j) for s in range(grid * 2 - 1) for i in range(grid) for j in range(grid) if i + j == s]
        slots = sorted(order, key=lambda ij: (max(abs(ij[0] - 1.5), abs(ij[1] - 1.5)), ij))
        for (i, j), kind in zip(slots, cells):
            sx = plot.centerx + (i - j) * tw // 2
            sy = top + (i + j) * th // 2 + th // 2 + 4
            rect = pygame.Rect(0, 0, 68, 79)
            rect.midbottom = (sx, sy + th // 2 + 2)
            tip = ("Town Hall", "Your home town.") if kind == "hall" else (D.BUILDINGS[kind]["name"],
                                                                          D.BUILDINGS[kind]["desc"])
            self.tips.append((rect.inflate(-10, -16), tip))

    # ---- zones and the Town -------------------------------------------------
    def env_cells(self):
        """Where each zone and the Town are on the board."""
        x0 = SIDE_W + 8
        cell_w = (W - 2 * SIDE_W - 16 - 16) // 3
        cell_h = CELL_H
        spots = D.BOARD_SPOTS
        out = {}
        for env, (i, j) in zip(self.game.envs, spots):
            out[env.eid] = pygame.Rect(x0 + i * (cell_w + 8), TOP_H + 6 + j * (cell_h + 6), cell_w, cell_h)
        out[TOWN] = pygame.Rect(x0 + cell_w + 8, TOP_H + 6 + cell_h + 6, cell_w, cell_h)
        return out

    def destination_clicks(self, key, rect):
        """While a human sends a pawn: make a zone clickable, or explain why it can't go there."""
        g = self.game
        if g.phase == "deploy" and not g.players[g.active].is_ai and self.selected:
            pawn = next((x for x in g.players[g.active].pawns if x.uid == self.selected), None)
            allowed, reason = g.can_send(g.active, key, pawn)
            if not allowed:
                self.tips.append((rect, ("Can't go here", reason)))
                return
            hover = rect.collidepoint(self.mouse)
            draw.rect(self.canvas, ACCENT_LIGHT if hover else CREAM, rect, 3 if hover else 1,
                             border_radius=9)
            self.click_zone(rect, lambda k=key: self.send_selected(k))

    def send_selected(self, destination):
        """Send the selected pawn there."""
        g = self.game
        g.send(g.active, self.selected, destination)
        self.selected = None
        self.fix_selection()

    def draw_location_pawns(self, key, rect):
        """The pawns standing in a zone or in the Town."""
        g = self.game
        pawns = [x for p in g.players for x in p.pawns if x.location == key]
        if not pawns:
            return
        step = min(30, (rect.w - 36) // len(pawns))
        total = step * (len(pawns) - 1)
        x = rect.centerx - total // 2
        for pawn in pawns:
            self.draw_pawn(pawn, x, rect.bottom - 9, 44)
            x += step

    def draw_env(self, env, rect):
        """A zone: its picture, what it gives, its prize, its mob and its event."""
        width = self.font(15, True).size(env.name)[0]  # the zone's picture is in the board's picture
        self.canvas.shade((rect.x + 3, rect.y + 3, width + 12, 21), (40, 28, 22, 190), 6)
        self.text(env.name, (rect.x + 9, rect.y + 13), 15, CREAM, True, "midleft")
        g = self.game
        known = g.known_mob(env)
        res, qty = env.prize
        chip = self.env_chip(rect, 28)
        self.text("Each pawn:", (chip.x + 7, chip.centery), 13, CREAM, True, "midleft")
        normal = env.harvest[0]
        self.chip_icon(normal, chip.x + 86, chip.y + 2)
        self.text(res_name(normal), (chip.x + 110, chip.centery), 13, CREAM, False, "midleft")
        chip = self.env_chip(rect, 54)
        self.text("Bonus:", (chip.x + 7, chip.centery), 13, (255, 226, 130), True, "midleft")
        self.chip_icon(res, chip.x + 57, chip.y + 2)
        self.text(f"x{qty}", (chip.x + 77, chip.centery), 13, (255, 226, 130), True, "midleft")
        if env.extra_food:
            self.chip_icon("food", chip.x + 100, chip.y + 2)
            self.text(f"+{env.extra_food}", (chip.x + 120, chip.centery), 13, (255, 226, 130), True, "midleft")
        if g.mob_hidden(env):
            self.text("Mob?", (chip.right - 7, chip.centery), 12, (255, 170, 150), True, "midright")
        elif env.friend:
            self.text("Friend", (chip.right - 7, chip.centery), 12, (190, 226, 170), True, "midright")
        elif known:
            short = env.extra_food and len(known[0]) > 6  # no room for a long name next to the Food
            label = f"Mob +{env.mob[1]}" if short else f"{known[0]} +{env.mob[1]}"
            self.text(label, (chip.right - 5, chip.centery), 11, (255, 170, 150), True, "midright")
        mob = (f"To win it, beat {known[0]}, who scores a die + {env.mob[1]}." if known
               else "The Fog hides any monster here." if g.mob_hidden(env)
               else f"{env.friend[1]} fight for {g.players[env.friend[0]].name} this turn." if env.friend
               else "")
        if known and g.mob_abilities and known[0] in D.MOB_ABILITIES:
            mob += " " + D.MOB_ABILITIES[known[0]]
        event = g.event_text(env.eid)
        extra = f" Event - {event[0]}: {event[1]}" if event else ""
        self.tips.append((rect, (env.name, f"Normal resource: each pawn collects 1 {res_name(normal)}. "
                                           f"Bonus prize: {g.prize_text(env)}, for one winner. {mob}{extra}")))
        self.draw_fight_bonus(env, rect)
        if known or env.friend:
            kind = D.MOB_SPRITES.get(known[0] if known else env.friend[1], "mob_gnoll")
            frame = int(self.clock_time * 8) + rect.x
            self.draw_unit(kind, "all", art.IDLE, frame, rect.right - 26, rect.bottom - 9, 42, True)
            if known and g.mob_abilities and known[0] in D.MOB_ABILITIES:
                self.tips.append((pygame.Rect(rect.right - 54, rect.bottom - 58, 54, 54),
                                  (f"{known[0]} (die + {env.mob[1]})", D.MOB_ABILITIES[known[0]])))
        self.draw_location_pawns(env.eid, rect)
        self.destination_clicks(env.eid, rect)
        self.draw_event_tag(env.eid, rect, rect.y + 3)

    def draw_event_tag(self, zone, rect, y):
        """The zone's permanent event, in a small label at the top right."""
        event = self.game.event_text(zone)
        if not event:
            return
        width = self.font(11, True).size(event[0])[0] + 12
        tag = pygame.Rect(rect.right - width - 4, y, width, 19)
        draw.rect(self.canvas, (120, 44, 30), tag, border_radius=6)
        self.text(event[0], tag.center, 11, (255, 226, 130), True, "center")
        self.tips.append((tag, event))
        rolled = next((e.event_die for e in self.game.envs if e.eid == zone and e.event_die), None)
        if rolled:  # this turn's die for the event
            value, ok = rolled
            spot = pygame.Rect(tag.x - 23, y, 19, 19)
            big = art.die(value, 40, (214, 240, 200) if ok else (246, 206, 196))
            self.canvas.blit(pygame.transform.smoothscale(big, (19, 19)), spot)
            self.tips.append((spot, (f"{event[0]} die: {value}",
                                     "+1 Food is added to the bonus prize this turn." if ok
                                     else "No extra Food this turn.")))

    def chip_icon(self, res, x, y):
        """A resource icon on a light disc, so dark icons stay readable."""
        draw.circle(self.canvas, CREAM, (x + 9, y + 9), 10)
        self.canvas.blit(art.resource_icon(res, 19), (x, y))

    def env_chip(self, rect, offset):
        """A dark label strip on a zone."""
        chip = pygame.Rect(rect.x + 6, rect.y + offset, rect.w - 12, 23)
        self.canvas.shade(chip, (40, 28, 22, 190), 7)
        return chip

    def bonus_text(self, pid, eid, vs_mob):
        """A player's fight bonuses in words, such as 'Watchtower +1'."""
        parts = self.game.strength_parts(pid, eid, vs_mob)
        return ", ".join(f"{label} {value:+d}" for label, value in parts)

    def draw_fight_bonus(self, env, rect):
        """Show each player's fight bonus once they have a pawn here."""
        g = self.game
        present = [p for p in g.players if g.fighters(p.pid, env.eid)]  # Raiders don't fight
        if not present:
            return
        chip = self.env_chip(rect, 80)
        self.canvas.blit(art.ui_icon("sword", 17) or art.resource_icon("gold", 17), (chip.x + 4, chip.y + 3))
        self.text("Fight:", (chip.x + 24, chip.centery), 12, CREAM, True, "midleft")
        x = chip.x + 62
        lines = []
        vs_mob = bool(g.known_mob(env))
        marks = self.settings["colorblind"]
        for p in present:
            value = g.strength(p.pid, env.eid, vs_mob)
            pill = pygame.Rect(x, chip.y + 3, 42 if marks else 30, 17)
            draw.rect(self.canvas, p.color, pill, border_radius=6)
            if marks:
                self.player_mark(p.team, pill.x + 10, pill.centery, 10, CREAM)
                self.text(f"+{value}", (pill.centerx + 6, pill.centery), 12, CREAM, True, "center")
            else:
                self.text(f"+{value}", pill.center, 12, CREAM, True, "center")
            x += pill.w + 2
            dice = g.dice_count(p.pid, env.eid)
            roll = f"best of {dice} dice" if dice > 1 else "a die"
            lines.append(f"{p.name}: {roll} + {value} ({self.bonus_text(p.pid, env.eid, vs_mob)}).")
        self.tips.append((chip, ("Fight bonus", " ".join(lines))))

    def draw_town(self, rect):
        """The Town tile in the middle of the board."""
        c = self.canvas
        c.blit(art.town_tile(rect.w, rect.h), rect)
        banner = pygame.Rect(rect.centerx - 34, rect.y + 3, 68, 22)
        draw.rect(c, TABLE_DARK, banner, border_radius=6)
        self.text("Town", banner.center, 15, CREAM, True, "center")
        self.tips.append((rect, ("Town", "One pawn per player. It can recruit one pawn and sell as often as you like.")))
        self.draw_location_pawns(TOWN, rect)
        self.destination_clicks(TOWN, rect)
        self.draw_event_tag(TOWN, rect, rect.bottom - 23)
        if any(x.info.get("sale_each") for p in self.game.players for x in self.game.pawns_at(p.pid, TOWN)):
            tag = pygame.Rect(rect.x + 4, rect.y + 3, 66, 20)
            draw.rect(c, ACCENT, tag, border_radius=6)
            self.text("Merchant", tag.center, 12, CREAM, True, "center")
            self.tips.append((tag, ("Merchant in town", "For its owner: +1 gold per item sold, recruits cost 1 less.")))

    # ---- top bar, toasts and banners ----------------------------------------
    def draw_top(self):
        """The top bar: the turn, the three steps and the buttons."""
        g = self.game
        c = self.canvas
        c.shade((0, 0, W, TOP_H), (30, 18, 12, 175))
        self.text(f"Turn {g.turn} of {g.max_turns}", (14, TOP_H // 2), 19, ACCENT_LIGHT, True, "midleft")
        x = 190
        for i, (phase, label) in enumerate(STEPS):
            active = g.phase == phase
            rect = pygame.Rect(x, 8, 190, 28)
            draw.rect(c, ACCENT if active else TABLE, rect, border_radius=14)
            self.text(f"{i + 1}. {label}", rect.center, 14, CREAM if active else (200, 180, 150), active, "center")
            x += 198
        self.draw_top_buttons()

    def draw_top_buttons(self):
        """The Settings, Zones, Buildings, Rules and Exit game buttons."""
        rect = pygame.Rect(W - 478, 6, 36, 32)
        self.button(rect, "", self.open_settings, size=14,
                    tip=("Settings", "Music and sound volume, the music, and help for colorblind players."))
        self.draw_gear(rect.centerx, rect.centery, INK)
        self.button((W - 334, 6, 128, 32), "Buildings", self.open_catalog, size=14, icon="hammer",
                    tip=("Buildings", "See every building and what it costs, at any time."))
        self.button((W - 202, 6, 86, 32), "Rules", self.open_rules, size=14, icon="scroll")
        self.button((W - 112, 6, 104, 32), "Exit game", lambda: setattr(self, "confirm_exit", True), size=14,
                    tip=("Exit game", "Stop this game and go back to the menu. You will be asked first."))
        self.button((W - 436, 6, 96, 32), "Zones", self.open_zones, size=14,
                    tip=("Zones", "See the resources, prizes and monsters each zone can have."))

    def open_settings(self):
        """Open or close the Settings window."""
        if self.modal == "settings":
            self.close_viewer()
        else:
            self.back_to = self.modal
            self.modal = "settings"

    def draw_gear(self, x, y, color):
        """A small cogwheel, for the Settings button: sound and colors."""
        points = []
        for i in range(24):  # 6 teeth: each one is 4 points, 2 out and 2 in
            angle = (i + 0.5) * math.pi / 12
            r = 11.5 if i % 4 in (1, 2) else 7.5
            points.append((x + r * math.cos(angle), y + r * math.sin(angle)))
        draw.polygon(self.canvas, color, points)
        draw.circle(self.canvas, CREAM, (x, y), 3.6)

    def change_setting(self, key, value):
        """Change a setting, use it at once and save it."""
        self.settings[key] = value
        settings.save(self.settings)
        if key == "music":
            self.music_volume = value
            if pygame.mixer.get_init() and not getattr(self, "muted", False):
                pygame.mixer.music.set_volume(value)
        elif key == "sounds":
            self.sounds.volume = value
            self.sounds.play("click")
        elif key == "track":
            self.play_music("game" if self.game else "menu")
        elif key == "colorblind":
            self.board_key = None  # the board's picture is drawn again

    def draw_settings(self, close=None):
        """The Settings window: volumes, the music, and the colorblind help."""
        self.dim()
        rect = pygame.Rect(W // 2 - 330, H // 2 - 200, 660, 400)
        self.panel(rect)
        self.text("Settings", (rect.x + 24, rect.y + 16), 24, INK, True)
        self.button((rect.right - 104, rect.y + 16, 90, 32), "Close", close or self.close_viewer, size=14)
        y = rect.y + 76
        for key, label in (("music", "Music volume"), ("sounds", "Sound effects")):
            self.text(label, (rect.x + 30, y + 16), 17, INK, True, "midleft")
            level = round(self.settings[key] * 10)
            x = rect.x + 230
            self.button((x, y, 34, 32), "-", lambda k=key, v=level: self.change_setting(k, max(0, v - 1) / 10),
                        level > 0, size=18)
            for i in range(10):
                bar = pygame.Rect(x + 44 + i * 26, y + 22 - (i + 1) * 2, 20, 10 + (i + 1) * 2)
                draw.rect(self.canvas, ACCENT if i < level else PAPER_DARK, bar, border_radius=3)
                draw.rect(self.canvas, TABLE_DARK, bar, 1, border_radius=3)
                self.hot.append((bar.inflate(6, 12), lambda k=key, v=i + 1: self.change_setting(k, v / 10)))
            self.button((x + 312, y, 34, 32), "+", lambda k=key, v=level: self.change_setting(k, min(10, v + 1) / 10),
                        level < 10, size=18)
            self.text(f"{level * 10}%" if level else "Off", (x + 358, y + 16), 15, MUTED, True, "midleft")
            y += 58
        self.text("Game music", (rect.x + 30, y + 18), 17, INK, True, "midleft")
        x = rect.x + 230
        for key, label in settings.TRACKS:
            self.button((x, y, 170, 36), label, lambda k=key: self.change_setting("track", k),
                        primary=self.settings["track"] == key, size=15)
            x += 180
        y += 50
        self.text("Village Medieval Music Pack by Leonardo Calvo.", (rect.x + 230, y), 12, MUTED)
        y += 40
        draw.line(self.canvas, MUTED, (rect.x + 24, y), (rect.right - 24, y), 1)
        y += 18
        self.text("Colorblind help", (rect.x + 30, y + 18), 17, INK, True, "midleft")
        on = self.settings["colorblind"]
        x = rect.x + 230
        for value, label in ((False, "Off"), (True, "On")):
            self.button((x, y, 80, 36), label, lambda v=value: self.change_setting("colorblind", v),
                        primary=on == value, size=15)
            x += 90
        y += 66
        palette = COLORBLIND if on else COLORS
        for i, team in enumerate(("red", "blue", "yellow", "purple")):  # each player's shape, in its color
            cx = rect.x + 120 + i * 140
            self.player_mark(team, cx, y, 22, palette[team])
            self.text(D.PLAYER_COLORS[i][0], (cx + 18, y), 15, INK, True, "midleft")

    def open_rules(self):
        """Open the rules window over whatever is open."""
        self.back_to = self.modal
        self.modal = "rules"

    def open_catalog(self):
        """Open or close the Buildings window."""
        if self.modal == "catalog":
            self.close_viewer()
        else:
            self.back_to = self.modal
            self.modal = "catalog"

    def open_zones(self):
        """Open or close the Zones window."""
        if self.modal == "zones":
            self.close_viewer()
        else:
            self.back_to = self.modal
            self.modal = "zones"

    def close_viewer(self):
        """Close a viewer window and go back to what was open before."""
        self.modal = self.back_to
        self.back_to = None

    def viewer(self):
        """Whose resources the building list compares against."""
        g = self.game
        if not g.players[g.active].is_ai:
            return g.active
        return next((p.pid for p in g.players if not p.is_ai), g.active)

    def draw_toast(self):
        """A short message about the last move."""
        if self.toast_time <= 0 or self.banners or self.modal or self.game.phase == "end":
            return
        width = self.font(19, True).size(self.toast)[0] + 44
        rect = pygame.Rect(0, 0, width, 46)
        rect.center = (W // 2, 516)
        self.panel(rect, CREAM, ACCENT)
        self.text(self.toast, rect.center, 19, INK, True, "center")

    def draw_unlock(self):
        """The message of an achievement just unlocked, at the top of the board."""
        if not self.unlocks:
            return
        key, name, shown = self.unlocks[0]
        text = achievements.BY_KEY[key][2]
        width = max(self.font(16, True).size(text)[0], 300) + 90
        rect = pygame.Rect(0, 0, width, 64)
        rect.midtop = (W // 2, 50 + min(0, round((shown - 0.25) * 240)))  # slides down from the top bar
        self.canvas.shade(rect.move(3, 4), (0, 0, 0, 90), 10)
        self.panel(rect, CREAM, ACCENT)
        self.draw_trophy(rect.x + 34, rect.centery, True)
        self.text(f"Achievement unlocked by {name}!", (rect.x + 66, rect.y + 12), 13, ACCENT, True)
        self.text(text, (rect.x + 66, rect.y + 32), 16, INK, True)

    def draw_trophy(self, x, y, unlocked):
        """A little cup: gold when unlocked, gray when not."""
        icon = art.resource_icon("relic", 30)
        if icon and not unlocked:
            icon = pygame.transform.grayscale(icon)
            icon.set_alpha(110)
        if icon:
            self.canvas.blit(icon, icon.get_rect(center=(x, y)))
        else:
            draw.circle(self.canvas, ACCENT if unlocked else PAPER_DARK, (x, y), 12)

    def draw_credits_page(self):
        """Menu page: who made the game, and whose art, music and sounds it uses."""
        box = pygame.Rect(W // 2 - 420, 30, 840, 740)
        self.panel(box)
        self.text("Credits", (box.centerx, box.y + 34), 26, INK, True, "center")
        y = box.y + 80
        for title, lines in CREDITS:
            self.text(title, (box.centerx, y), 18, ACCENT, True, "center")
            y += 28
            for line in lines:
                self.credit_line(line, box, y)
                y += 22
            y += 14
        self.text("Thank you for playing!", (box.centerx, box.bottom - 96), 16, MUTED, True, "center")
        self.button((box.centerx - 80, box.bottom - 64, 160, 44), "Back", lambda: setattr(self, "page", "start"), size=16)

    def credit_line(self, line, box, y):
        """One centered credits line; a (text, link) line ends with a clickable, underlined link."""
        if isinstance(line, str):
            self.text(line, (box.centerx, y), 14, INK, False, "center")
            return
        text, url = line
        shown = url if len(url) < 52 else url[:49] + "..."  # long links are shortened on screen
        tw, lw = self.font(14).size(text)[0], self.font(14, True).size(shown)[0]
        x = box.centerx - (tw + lw) // 2
        self.text(text, (x, y), 14, INK, False, "midleft")
        link = pygame.Rect(x + tw, y - 10, lw, 21)
        hover = link.collidepoint(self.mouse)
        self.text(shown, (link.x, y), 14, ACCENT if hover else LINK, True, "midleft")
        draw.line(self.canvas, ACCENT if hover else LINK, (link.x, link.bottom - 1), (link.right, link.bottom - 1), 1)
        self.hot.append((link, lambda: open_link("https://" + url)))
        if hover:
            self.tips.append((link, ("Open in your browser", "https://" + url)))

    def draw_achievements_page(self):
        """Menu page: every achievement, unlocked or not."""
        box = pygame.Rect(W // 2 - 590, 40, 1180, 720)
        self.panel(box)
        got = self.achievements.unlocked
        total = len(achievements.ACHIEVEMENTS)
        self.text("Achievements", (box.centerx, box.y + 30), 26, INK, True, "center")
        self.text(f"{len(got)} of {total} unlocked", (box.centerx, box.y + 60), 15, MUTED, False, "center")
        columns = (achievements.GROUPS[:3], achievements.GROUPS[3:])
        for col, groups in enumerate(columns):
            x, y = box.x + 30 + col * 580, box.y + 92
            for group in groups:
                self.text(group, (x, y), 18, ACCENT, True)
                y += 28
                for key, _, text, _, _ in (a for a in achievements.ACHIEVEMENTS if a[1] == group):
                    done = got.get(key)
                    row = pygame.Rect(x, y, 550, 28)
                    if done:
                        draw.rect(self.canvas, (234, 244, 214), row, border_radius=6)
                    self.draw_trophy(x + 16, y + 14, bool(done))
                    self.text(text, (x + 38, y + 14), 14, INK if done else MUTED, bool(done), "midleft")
                    if done:
                        self.tips.append((row, (text, f"Unlocked by {done['name']} on {done['date']}.")))
                    y += 31
                y += 10
        self.button((box.x + 30, box.bottom - 58, 160, 44), "Back", lambda: setattr(self, "page", "start"), size=16)

    def draw_banner(self):
        """The big announcement of a new step or turn."""
        if not self.banners or self.modal in VIEWERS:
            return
        self.tips = []
        rect = pygame.Rect(0, 0, 620, 74)
        rect.center = (W // 2, H // 2 - 80)
        self.panel(rect, TABLE_DARK, ACCENT_LIGHT)
        self.text(self.banners[0], rect.center, 24, CREAM, True, "center")

    # ---- bottom bar and step 2 actions --------------------------------------
    def draw_bottom(self):
        """The prices of today's market."""
        g = self.game
        c = self.canvas
        x0 = SIDE_W + 8
        y0 = H - 6 - PRICE_H
        rect = pygame.Rect(x0, y0, W - 2 * SIDE_W - 16, PRICE_H)  # its paper is in the board's picture
        self.text("Prices today", (rect.x + 12, rect.centery), 13, MUTED, True, "midleft")
        for i, r in enumerate(D.RESOURCE_IDS):
            x = rect.x + 106 + i * 54
            y = rect.centery - 11
            c.blit(art.resource_icon(r, 21), (x, y))
            base = D.RESOURCES[r][1]
            price = g.prices[r]
            color = GOOD if price > base else BAD if price < base else INK
            self.text(price, (x + 24, y + 11), 15, color, True, "midleft")
            if price != base:  # an arrow: up when it sells for more than usual, down for less
                ax = x + 28 + self.font(15, True).size(str(price))[0] + 2
                up = price > base
                tip_y, foot = (y + 5, y + 14) if up else (y + 17, y + 8)
                draw.polygon(c, color, [(ax, foot), (ax + 9, foot), (ax + 4.5, tip_y)])
            self.tips.append((pygame.Rect(x, y, 50, 22), (D.RESOURCES[r][0],
                              f"Sells for {price} gold today" + (f" (usually {base})." if price != base else ", as usual."))))

    def free_cell(self, cells):
        """The empty place under the Town."""
        return cells[TOWN].move(0, cells[TOWN].h + 6)

    def draw_actions(self, rect):
        """The player's buttons, in the free space of the table."""
        g = self.game
        pid = g.active
        if g.players[pid].is_ai or g.phase not in ("deploy", "actions"):
            return
        rect = rect.inflate(-16, -16)
        if g.phase == "deploy":
            rows = [("Keep pawn home", self.keep_selected, bool(self.selected), False, None, None)]
        else:
            rows = [("Build", lambda: setattr(self, "modal", "build"), bool(g.free_home(pid)) or self.has_alchemy(),
                     False, "hammer", None),
                    ("Town", self.open_town, bool(g.free_town(pid) or g.free_sellers(pid)), False, None, None)]
            if self.has_alchemy():
                rows.append(("Alchemy", lambda: setattr(self, "modal", "alchemy"),
                             g.can_transmute(pid) or g.can_use_lab(pid) or g.can_swap(pid), False, None,
                             ("Alchemy", "Transform resources. Your pawns can still build.")))
            if g.can_horn(pid):
                chosen = g.players[pid].horn
                label = f"Slinger: {g.env(chosen).name}" if chosen else "Stone Slinger"
                rows.append((label, lambda: setattr(self, "modal", "horn"), True, False, None,
                             ("Stone Slinger", "Choose one zone next to the Stone Slinger: your pawns there get +1 "
                              "in the fight, but the Stone Slinger then adds nothing to its own fight.")))
            rows.append(("End", self.press_end, True, True, None, None))
        height = min(44, (rect.h - (len(rows) - 1) * 6) // len(rows))
        top = rect.centery - (height * len(rows) + 6 * (len(rows) - 1)) // 2
        for i, (label, action, enabled, primary, icon, tip) in enumerate(rows):
            self.button((rect.x, top + i * (height + 6), rect.w, height), label, action, enabled, primary,
                        size=16, icon=icon, tip=tip)

    def press_end(self):
        """Check first if the player forgot something."""
        g = self.game
        if g.remaining_actions(g.active):
            self.modal = "end_check"
        else:
            g.end_actions(g.active)

    def draw_end_check(self):
        """'End your turn?' when there is still something to do."""
        g = self.game
        pid = g.active
        left = g.remaining_actions(pid)
        self.dim()
        lines = [line for item in left for line in self.wrap(item, 440, 16)]
        rect = pygame.Rect(W // 2 - 260, H // 2 - 110, 520, 158 + len(lines) * 26)
        self.panel(rect)
        self.text("End your turn?", (rect.centerx, rect.y + 30), 23, INK, True, "center")
        self.text("You can still:", (rect.x + 30, rect.y + 62), 15, MUTED, True)
        for i, line in enumerate(lines):
            self.text(line, (rect.x + 30, rect.y + 90 + i * 26), 16, INK, True)
        y = rect.bottom - 54
        self.button((rect.x + 30, y, 215, 40), "Back", lambda: setattr(self, "modal", None), size=15)
        self.button((rect.right - 245, y, 215, 40), "End turn", self.confirm_end, primary=True, size=15)

    def draw_horn(self):
        """Choose the zone the Stone Slinger helps."""
        g = self.game
        pid = g.active
        zones = g.horn_zones(pid)
        self.dim()
        rect = pygame.Rect(W // 2 - 230, H // 2 - 60 - 23 * len(zones), 460, 130 + 46 * len(zones))
        self.panel(rect)
        self.text("Stone Slinger", (rect.centerx, rect.y + 28), 22, INK, True, "center")
        self.text("Your pawns in this zone get +1 in the fight.", (rect.centerx, rect.y + 56), 14, MUTED, False,
                  "center")
        for i, eid in enumerate(zones):
            self.button((rect.x + 40, rect.y + 78 + i * 46, rect.w - 80, 38), g.env(eid).name,
                        lambda e=eid: self.choose_horn(e), primary=g.players[pid].horn == eid, size=15)
        self.button((rect.centerx - 46, rect.bottom - 44, 92, 32), "Close", lambda: setattr(self, "modal", None),
                    size=14)

    def choose_horn(self, eid):
        """The Stone Slinger helps this zone."""
        self.game.set_horn(self.game.active, eid)
        self.modal = None

    def confirm_end(self):
        """End step 2 for this player."""
        self.modal = None
        self.game.end_actions(self.game.active)

    def keep_selected(self):
        """Keep the selected pawn at home."""
        g = self.game
        g.keep_home(g.active, self.selected)
        self.selected = None
        self.fix_selection()

    # ---- alchemy ------------------------------------------------------------
    def has_alchemy(self):
        """Does the active player have a pawn at home that can transform?"""
        g = self.game
        pid = g.active
        alchemist = g.free_alchemists(pid)
        lab = g.players[pid].has_effect("herb_lab") and g.lab_pawns(pid)
        return bool(alchemist or lab or g.shaman_swaps_left(pid))

    def alchemy_rows(self):
        """Each row: title, then (source, result, how many, action, allowed)."""
        g = self.game
        pid = g.active
        rows = []
        if g.free_alchemists(pid):
            rows.append(("Goblin Alchemist", [(s, r, 1, lambda r=r: self.do_transmute(r), g.can_transmute(pid, r))
                                              for r, s in D.ALCHEMY.items()]))
        if g.players[pid].has_effect("herb_lab") and g.lab_pawns(pid):
            rows.append(("Alchemy Lab", [("herbs", r, n, lambda r=r: self.do_lab(r), g.can_use_lab(pid, r))
                                         for r, n in D.LAB_RESULTS.items()]))
        left = g.shaman_swaps_left(pid)
        if left:
            rows.append((f"Skull Shaman ({left} left this turn)",
                         [(a, b, 1, lambda a=a, b=b: g.swap(pid, a, b), g.can_swap(pid, a, b))
                          for a in D.BASIC_RESOURCES for b in D.BASIC_RESOURCES if a != b]))
        return rows

    def draw_alchemy_modal(self):
        """The Alchemy Lab and Alchemist window."""
        rows = self.alchemy_rows()
        self.dim()
        height = 76 + 116 * len(rows)
        width = 176
        most = max((len(options) for _, options in rows), default=1)
        panel_width = max(600, most * (width + 10) + 30)
        rect = pygame.Rect(W // 2 - panel_width // 2, H // 2 - height // 2, panel_width, height)
        self.panel(rect)
        y = rect.y + 12
        for title, options in rows:
            self.text(title, (rect.centerx, y + 14), 20, INK, True, "center")
            x = rect.centerx - (len(options) * (width + 10) - 10) // 2
            for source, res, made, action, allowed in options:
                label = f"{res_name(source)} to {made} {res_name(res)}" if made > 1 else f"{res_name(source)} to {res_name(res)}"
                self.canvas.blit(art.resource_icon(source, 26), (x + 42, y + 34))
                self.text(">", (x + 88, y + 47), 16, INK, True, "center")
                self.canvas.blit(art.resource_icon(res, 26), (x + 108, y + 34))
                self.button((x, y + 66, width, 36), label, action, allowed, size=14)
                x += width + 10
            y += 116
        self.button((rect.centerx - 46, rect.bottom - 50, 92, 32), "Close",
                    lambda: setattr(self, "modal", None), size=14)

    def do_lab(self, res):
        """Use the Alchemy Lab."""
        self.modal = None
        self.game.use_lab(self.game.active, res)

    def do_transmute(self, res):
        """Use an Alchemist."""
        self.modal = None
        self.game.transmute(self.game.active, res)

    def open_town(self):
        """Open the town window (recruit and sell)."""
        self.lots = {}
        self.modal = "town"

    # ---- the whole board ----------------------------------------------------
    def draw_game(self):
        """The whole board: table, zones, Town, players' panels and the bottom bar."""
        g = self.game
        palette = COLORBLIND if self.settings["colorblind"] else COLORS
        for player in g.players:  # the colorblind help changes the players' colors
            player.color = palette.get(player.team, player.color)
        self.draw_board_background()
        self.draw_top()
        for player, rect in zip(g.players, self.base_rects()):
            self.draw_base(player, rect)
        cells = self.env_cells()
        for env in g.envs:
            self.draw_env(env, cells[env.eid])
        self.draw_town(cells[TOWN])
        self.draw_bottom()
        self.draw_actions(self.free_cell(cells))

    def draw_board_background(self):
        """The parts of the board that don't move (the table, the zones' pictures, the players' panels and
        their buildings) are drawn once into a picture, then copied each frame: far less work, which keeps
        the browser version smooth. The picture is drawn again when a building is added."""
        g = self.game
        key = (self.canvas.get_size(), tuple((p.team, p.color, tuple(p.buildings)) for p in g.players),
               tuple(e.eid for e in g.envs))
        if getattr(self, "board_key", None) != key:
            screen, tips = self.canvas, self.tips
            self.canvas = Screen(screen.get_size(), screen.scale)
            wood = art.table()
            if wood:
                self.canvas.blit(wood, (0, 0))
            else:
                self.canvas.fill(TABLE)
            for player, rect in zip(g.players, self.base_rects()):
                self.panel(rect, PAPER, TABLE_DARK)
                head = pygame.Rect(rect.x + 4, rect.y + 5, rect.w - 8, 34)
                band = art.ribbon(player.team, head.w, head.h)
                if band:
                    self.canvas.blit(band, head)
                else:
                    draw.rect(self.canvas, player.color, head, border_radius=7)
                self.draw_plot(player, self.plot_rect(rect))
            self.panel((SIDE_W + 8, H - 6 - PRICE_H, W - 2 * SIDE_W - 16, PRICE_H))
            cells = self.env_cells()
            for env in g.envs:
                rect = cells[env.eid]
                self.canvas.blit(art.environment(env.eid, rect.w, rect.h), rect)
                draw.rect(self.canvas, TABLE_DARK, rect, 2, border_radius=8)
            self.board_picture, self.board_key = self.canvas, key
            self.canvas, self.tips = screen, tips
        pygame.Surface.blit(self.canvas, self.board_picture, (0, 0))

    def plot_rect(self, rect):
        """Where a player's realm is in their panel."""
        return pygame.Rect(rect.x + 6, rect.y + 92, rect.w - 12, rect.h - 146)

    # ---- modals -------------------------------------------------------------
    def dim(self):
        """Darken the screen behind a window and stop clicks on the board."""
        self.canvas.shade((0, 0, W, H), (20, 12, 8, 165))
        self.hot = []
        self.tips = []

    # ---- building window ----------------------------------------------------
    def draw_build(self, catalog=False):
        """The building window: the tree of all buildings, costs and what you own."""
        g = self.game
        pid = self.viewer() if catalog else g.active
        p = g.players[pid]
        self.dim()
        rect = pygame.Rect(20, 16, W - 40, H - 32)
        self.panel(rect)
        if catalog:
            self.text("Buildings", (rect.x + 18, rect.y + 12), 21, INK, True)
            self.text("Hover a building to see what it does.",
                      (rect.x + 150, rect.y + 18), 14, MUTED)
            self.button((rect.right - 106, rect.y + 10, 92, 32), "Close", self.close_viewer, size=14)
        else:
            count = min(len(g.free_home(pid)), D.MAX_BUILDINGS - len(p.buildings))  # each free pawn builds once
            self.text(f"{p.name}: choose {count} building{'s' if count > 1 else ''}", (rect.x + 18, rect.y + 12),
                      21, INK, True)
            self.button((rect.right - 106, rect.y + 10, 92, 32), "Close", lambda: setattr(self, "modal", None), size=14)
        self.draw_tree(rect, pid, catalog)
        if not catalog:
            self.draw_discounts(rect, pid)

    def tree_lanes(self, nodes):
        """Where each building's line turns: lines that share a height never share a lane."""
        children = {}
        for bid in nodes:
            for need in D.requirements(bid):
                children.setdefault(need, []).append(nodes[bid])
        lanes = {}
        for tier in {D.BUILDINGS[b]["tier"] for b in children}:
            spans = []
            for need, kids in children.items():
                if D.BUILDINGS[need]["tier"] == tier:
                    heights = [nodes[need].centery] + [k.centery for k in kids]
                    spans.append((min(heights), max(heights), need))
            ends = []
            placed = {}
            for top, bottom, need in sorted(spans):
                lane = next((i for i, end in enumerate(ends) if end + 12 < top), len(ends))
                ends[lane:lane + 1] = [bottom]
                placed[need] = lane
            for need, lane in placed.items():
                left = nodes[need].right
                gap = min(k.left for k in children[need]) - left
                lanes[need] = left + gap * (lane + 1) // (len(ends) + 1)
        return lanes

    def merging_links(self, nodes):
        """Lines into one building from 3 or more others (the Castle) share one turning lane, so they meet
        at one point like the Guild Hall's two lines, and never cross."""
        paths = {}
        for bid, child in nodes.items():
            needs = D.requirements(bid)
            if len(needs) < 3 or any(sum(n in D.requirements(k) for k in nodes) > 1 for n in needs):
                continue  # one or two lines, or a parent whose line also goes elsewhere
            left = max(nodes[n].right for n in needs)
            lane = (left + child.left) // 2
            for n in needs:
                paths[(n, bid)] = self.tree_link(nodes[n].midright, child.midleft, lane)
        return paths

    def tree_link(self, start, end, bend):
        """A straight line with softly cut corners."""
        if start[1] == end[1]:
            return [start, end]
        step = 5 if end[1] > start[1] else -5
        if abs(end[1] - start[1]) < 12:
            return [start, (bend, start[1]), (bend, end[1]), end]
        return [start, (bend - 5, start[1]), (bend, start[1] + step), (bend, end[1] - step), (bend + 5, end[1]), end]

    def draw_discounts(self, rect, pid):
        """The Mason, Workshop and Dwarf Builder choices, in the free space under the tier 4 buildings.
        The Workshop adds to the Mason or the Dwarf Builder; the Mason and the Dwarf Builder don't add up."""
        g = self.game
        p = g.players[pid]
        masons = any(x.info.get("half_build") and not x.new for x in g.pawns_at(pid, HOME))
        rows = []
        if p.halved or (masons and g.masons_left(pid) > 0):
            rows.append(("Mason", "half", D.MASON_RESOURCES, p.halved))
        if p.has_effect("half_build") and (p.ws_halved or not p.ws_used):
            rows.append(("Workshop", "half", D.MASON_RESOURCES, p.ws_halved))
        if p.trimmed or g.can_trim(pid):
            rows.append(("Dwarf Builder", "-1", D.BASIC_RESOURCES, p.trimmed))
        if not rows or not g.free_home(pid):
            return
        fourth = [b for b in D.BUILDINGS if D.BUILDINGS[b]["tier"] == 4]
        top = rect.y + 70 + (9 - len(fourth)) * 77 // 2 + (len(fourth) - 1) * 77 + 72 + 12
        box = pygame.Rect(rect.x + 14 + 3 * 246, top, rect.right - 18 - (rect.x + 14 + 3 * 246), rect.bottom - 12 - top)
        self.panel(box, CREAM, MUTED, 8)
        self.text("Discounts on your next building", (box.x + 12, box.y + 8), 16, INK, True)
        for i, (who, kind, resources, chosen) in enumerate(rows):
            y = box.y + 34 + i * 44
            label = f"{who}: {kind} {res_name(chosen)}" if chosen else f"{who}: {kind}"
            self.text(label, (box.x + 12, y + 19), 15, GOOD if chosen else INK, True, "midleft")
            for k, res in enumerate(resources):
                spot = (box.right - 12 - (len(D.MASON_RESOURCES) - k) * 50, y, 46, 38)
                if who == "Mason":
                    ok = g.can_halve(pid, "mason")
                    why = ("The Dwarf Builder already lowers your next building: the Mason and the Dwarf Builder "
                           "don't add up." if p.trimmed else "The next building costs half of this resource, rounded up. "
                           "Adds to the Workshop, even on the same resource. Lasts until you build or the turn ends.")
                    act = lambda r=res: g.use_mason(pid, r, "mason")
                    title = f"Mason: half {res_name(res)}"
                elif who == "Workshop":
                    ok = g.can_halve(pid, "workshop")
                    why = ("The next building costs half of this resource, rounded up. Adds to the Mason or the "
                           "Dwarf Builder. Once per turn.")
                    act = lambda r=res: g.use_mason(pid, r, "workshop")
                    title = f"Workshop: half {res_name(res)}"
                else:
                    ok = g.can_trim(pid) and not p.halved
                    why = ("The Mason already halves your next building: the Mason and the Dwarf Builder don't "
                           "add up." if p.halved else "The next building costs 1 less of this resource. Adds to "
                           "the Workshop. Once per turn.")
                    act = lambda r=res: g.use_trim(pid, r)
                    title = f"Dwarf Builder: -1 {res_name(res)}"
                self.button(spot, "", act, ok, primary=res == chosen, tip=(title, why))
                self.canvas.blit(art.resource_icon(res, 30), (spot[0] + 8, spot[1] + 4))
        if any(x.info.get("trim_build") for x in p.pawns):
            self.text("The Mason and the Dwarf Builder can't be used on the same building.", (box.x + 12, box.bottom - 10), 11, MUTED, False, "midleft")

    def tree_nodes(self, rect):
        """Lay out the buildings in one column per tier."""
        node_w, node_h, pitch_x, pitch_y = 204, 72, 246, 77
        top = rect.y + 70
        tiers = {}
        for bid, info in D.BUILDINGS.items():
            tiers.setdefault(info["tier"], []).append(bid)
        nodes = {}
        for tier, ids in tiers.items():
            x = rect.x + 14 + (tier - 1) * pitch_x
            start = top + (9 - len(ids)) * pitch_y // 2
            for row, bid in enumerate(ids):
                nodes[bid] = pygame.Rect(x, start + row * pitch_y, node_w, node_h)
            self.text(f"Tier {tier}", (x + node_w // 2, rect.y + 56), 14, MUTED, True, "center")
        for bid in tiers[1]:  # each tier 1 building faces the middle of what it unlocks, so lines never cross
            kids = [nodes[k].centery for k in nodes if bid in D.requirements(k)]
            if kids:
                nodes[bid].centery = sum(kids) // len(kids)
        return nodes

    def draw_stock(self, rect, p):
        """The player's resources, beside the building tree."""
        c = self.canvas
        self.panel(rect, CREAM, MUTED, 8)
        self.player_name(p, f"{p.name}'s resources", (rect.x + 10, rect.y + 8), 14, p.color, True, "topleft")
        for i, r in enumerate(D.RESOURCE_IDS):  # 4 per row, to leave room for the Farm below
            x = rect.x + 8 + (i % 4) * 48
            y = rect.y + 30 + (i // 4) * 24
            n = p.res[r]
            c.blit(art.resource_icon(r, 22) if n else art.faded_icon(r, 22), (x, y))
            self.text(n, (x + 25, y + 11), 15, INK if n else MUTED, n > 0, "midleft")
            self.tips.append((pygame.Rect(x, y, 46, 22), (D.RESOURCES[r][0], "")))

    def draw_tree(self, rect, pid, catalog):
        """The building tree: one card per building, with lines to what it unlocks."""
        g = self.game
        p = g.players[pid]
        c = self.canvas
        nodes = self.tree_nodes(rect)
        lanes = self.tree_lanes(nodes)
        links = [(bid, need) for bid in nodes for need in D.requirements(bid)]
        links.sort(key=lambda link: (nodes[link[0]].collidepoint(self.mouse), link[1] in p.buildings))
        merging = self.merging_links(nodes)
        for bid, need in links:
            hovered = nodes[bid].collidepoint(self.mouse)
            color = INK if hovered else GOOD if need in p.buildings else MUTED
            path = merging.get((need, bid)) or self.tree_link(nodes[need].midright, nodes[bid].midleft, lanes[need])
            draw.lines(c, color, False, path, 3 if hovered else 2)
        self.draw_stock(pygame.Rect(rect.x + 14, rect.y + 72, 204, STOCK_H), p)
        for bid, node in nodes.items():
            info = D.BUILDINGS[bid]
            owned = p.count(bid)
            missing = g.missing_requirements(pid, bid)
            allowed, reason = g.can_build(pid, bid)
            clickable = allowed and not catalog
            ready = g.can_pay_for(pid, bid)
            if missing:
                fill, edge = PAPER_DARK, MUTED
            elif owned:
                fill, edge = (226, 240, 210), MUTED
            else:
                fill, edge = (250, 240, 218), MUTED
            if ready:
                fill, edge = CREAM, GOOD
            draw.rect(c, fill, node, border_radius=8)
            draw.rect(c, edge, node, 4 if ready else 2, border_radius=8)
            c.blit(art.building_at(info["style"], p.color, 50, 58), (node.x + 3, node.y + 7))
            self.text(info["name"], (node.x + 56, node.y + 5), 13, MUTED if missing else INK, True)
            self.res_cost(g.build_cost(pid, bid), node.x + 56, node.y + 26, p.res, 16)
            self.text(f"Owned {owned}/{info['max']}", (node.x + 56, node.y + 50), 11, MUTED)
            value = D.building_vp(bid)
            self.text(f"{value} VP", (node.right - 8, node.y + 50), 12, ACCENT, True, "topright")
            body = f"{info['desc']} Worth {value} VP at game end."
            if missing:
                body += f" {g.needs_text(pid, bid)}."
            elif not catalog and reason:
                body += f" {reason}."
            self.tips.append((node, (info["name"], body)))
            if clickable:
                self.click_zone(node, lambda b=bid: self.do_build(b))

    def do_build(self, bid):
        """Build, first asking which pawn leaves if a free Peasant would go over the limit."""
        g = self.game
        if D.BUILDINGS[bid].get("free_peasant") and g.must_dismiss(g.active):
            self.swap = ("build", bid)  # a full roster chooses: replace a pawn, or no Peasant
            self.modal = "dismiss"
            return
        self.finish_build(bid)

    def finish_build(self, bid, dismiss=None):
        """Build, then close the window when nothing more can be built."""
        g = self.game
        pid = g.active
        self.modal = "build"
        g.build(pid, bid, dismiss)
        if g.phase != "actions" or g.active != pid or not g.free_home(pid):
            self.modal = None

    # ---- town window: recruit and sell --------------------------------------
    def draw_town_modal(self):
        """The town window: recruits on offer and the market."""
        g = self.game
        pid = g.active
        p = g.players[pid]
        self.dim()
        rect = pygame.Rect(70, 44, W - 140, H - 88)
        self.panel(rect)
        self.text(f"{p.name} in town", (rect.x + 20, rect.y + 13), 22, INK, True)
        sellers = len(g.free_sellers(pid))
        title_w = self.font(22, True).size(f"{p.name} in town")[0]
        gold_text = f"{p.gold} gold"
        purse = pygame.Rect(rect.x + 40 + title_w, rect.y + 9, self.font(22, True).size(gold_text)[0] + 56, 38)
        draw.rect(self.canvas, PAPER_DARK, purse, border_radius=19)  # your gold, easy to see
        draw.rect(self.canvas, ACCENT, purse, 2, border_radius=19)
        coin = art.resource_icon("gold", 28)
        if coin:
            self.canvas.blit(coin, (purse.x + 8, purse.y + 5))
        self.text(gold_text, (purse.x + 42, purse.centery), 22, INK, True, "midleft")
        if g.caravan_recruit(pid):
            self.text("Caravan Post: +1 recruit", (purse.right + 16, purse.centery), 14, MUTED, False, "midleft")
        self.button((rect.right - 104, rect.y + 11, 90, 32), "Close", lambda: setattr(self, "modal", None), size=14)
        self.text("Recruit", (rect.x + 20, rect.y + 54), 18, INK, True)
        if any(x.info.get("recruit_discount") for x in g.free_town(pid)):
            self.text("Merchant in town: recruits cost 1 less", (rect.x + 96, rect.y + 58), 14, GOOD, True)
        for i, kind in enumerate(g.recruits[pid]):
            x = rect.x + 20
            y = rect.y + 82 + i * 138
            card = pygame.Rect(x, y, 540, 130)
            draw.rect(self.canvas, (250, 240, 218) if kind else PAPER_DARK, card, border_radius=8)
            draw.rect(self.canvas, MUTED, card, 1, border_radius=8)
            if not kind:
                self.text("Recruited", card.center, 15, MUTED, False, "center")
                continue
            frame = int(self.clock_time * 8) + i
            self.draw_unit(kind, p.team, art.IDLE, frame, x + 48, y + 106, 72)
            info = D.PAWNS[kind]
            self.text(info["name"], (x + 92, y + 12), 17, INK, True)
            bottom = self.para(info["desc"], x + 92, y + 40, 280, 14)
            self.text(f"{D.pawn_vp(kind)} VP at game end", (x + 92, bottom + 4), 13, ACCENT, True)
            cost = g.recruit_cost(pid, i)
            allowed, reason = g.can_recruit(pid, i)
            self.canvas.blit(art.resource_icon("gold", 24), (x + 390, y + 12))
            self.text(cost, (x + 420, y + 24), 19, INK if p.gold >= cost else BAD, True, "midleft")
            label = "Replace a pawn" if g.must_dismiss(pid) else "Recruit"
            self.button((x + 390, y + 48, 136, 36), label, lambda i=i: self.do_recruit(i), allowed, True, size=14)
            if reason:
                self.text(reason, (x + 390, y + 92), 12, BAD)
        sx = rect.x + 586
        self.text("Sell", (sx, rect.y + 54), 18, INK, True)
        stall = p.building_sum("sale_bonus")
        merchant = any(x.info.get("sale_each") for x in g.free_sellers(pid))
        bonuses = ([f"Market Stall: +{stall} per sale"] if stall else []) + (["Merchant: +1 per item"] if merchant else [])
        if bonuses:
            self.text("   ".join(bonuses), (sx + 56, rect.y + 54), 14, GOOD, True)
        heads = ((sx + 118, "chest", "What you have"), (sx + 184, "gold", "Price today"))
        for hx, icon, name in heads:
            self.canvas.blit(art.ui_icon(icon, 18), (hx, rect.y + 66))
            self.tips.append((pygame.Rect(hx, rect.y + 66, 18, 18), (name, "")))
        for i, r in enumerate(D.RESOURCE_IDS):
            y = rect.y + 82 + i * 45
            n = self.lots.get(r, 0)
            self.canvas.blit(art.resource_icon(r, 28), (sx, y))
            self.text(D.RESOURCES[r][0], (sx + 36, y + 14), 15, INK, False, "midleft")
            self.text(p.res[r], (sx + 127, y + 14), 15, INK if p.res[r] else MUTED, p.res[r] > 0, "center")
            self.text(g.prices[r], (sx + 193, y + 14), 15, INK, False, "center")
            self.button((sx + 262, y, 32, 30), "-", lambda r=r: self.change_lot(r, -1), n > 0)
            self.text(n, (sx + 314, y + 15), 17, INK, True, "center")
            self.button((sx + 334, y, 32, 30), "+", lambda r=r: self.change_lot(r, 1), n < p.res[r])
            self.button((sx + 374, y, 56, 30), "All", lambda r=r: self.lots.__setitem__(r, p.res[r]),
                        p.res[r] > 0, size=13)
        value = g.sale_value(pid, self.lots)
        y = rect.bottom - 56
        self.text(f"Total: {value} gold", (sx, y + 20), 19, INK, True, "midleft")
        self.button((sx + 278, y, 152, 40), "Sell selected", self.do_sell, value > 0 and sellers > 0, True, size=15)

    def draw_exit_confirm(self):
        """Exit game asks first: the game in progress is lost, and you go back to the menu."""
        self.hot = []
        self.tips = []
        self.canvas.shade((0, 0, W, H), (20, 12, 8, 150))
        box = pygame.Rect(W // 2 - 230, H // 2 - 90, 460, 180)
        self.panel(box)
        tutorial = self.confirm_exit == "tutorial"
        self.text("Quit the tutorial?" if tutorial else "Stop this game?", (box.centerx, box.y + 36), 22, INK, True,
                  "center")
        self.text("You go back to the choice of game." if tutorial else "It will be lost, and you go back to the menu.",
                  (box.centerx, box.y + 74), 16, MUTED, False, "center")
        self.button((box.centerx - 170, box.bottom - 62, 150, 44), "Cancel",
                    lambda: setattr(self, "confirm_exit", False), size=16)
        self.button((box.centerx + 20, box.bottom - 62, 150, 44), "Quit" if tutorial else "Exit game", self.exit_to_menu,
                    primary=True, size=16)

    def exit_to_menu(self):
        """Confirmed: leave the game for the start screen, or the tutorial for the choice of game."""
        tutorial = self.confirm_exit == "tutorial"
        self.confirm_exit = False
        self.modal = None
        self.back_to_menu()
        if tutorial:
            self.page = "mode"

    def change_lot(self, r, delta):
        """One more or one less of a resource to sell."""
        self.lots[r] = self.lots.get(r, 0) + delta

    def after_town(self, pid):
        """The town window closes once nothing is left to do there."""
        g = self.game
        self.lots = {}
        recruit = g.free_town(pid) or g.caravan_recruit(pid)
        sell = g.free_sellers(pid) and any(g.players[pid].res.values()) and not g.has_sold(pid)
        if g.phase != "actions" or g.active != pid or not (recruit or sell):
            self.modal = None

    def do_recruit(self, index):
        """Recruit, first asking which pawn leaves if you are at the limit."""
        pid = self.game.active
        if self.game.must_dismiss(pid):
            self.swap = ("recruit", index)
            self.modal = "dismiss"
            return
        self.game.recruit(pid, index)
        self.after_town(pid)

    def do_dismiss(self, uid):
        """The pawn that leaves to make room, then finish the recruit or the build."""
        kind, value = self.swap
        if kind == "recruit":
            pid = self.game.active
            self.modal = "town"
            self.game.recruit(pid, value, uid)
            self.after_town(pid)
        else:
            self.finish_build(value, uid)

    def draw_dismiss(self):
        """A full roster: choose who leaves for the new recruit."""
        g = self.game
        pid = g.active
        p = g.players[pid]
        self.dim()
        rect = pygame.Rect(W // 2 - 400, H // 2 - 220, 800, 440)
        self.panel(rect)
        kind, value = self.swap
        new = "Peasant" if kind == "build" else D.PAWNS[g.recruits[pid][value]]["name"]
        self.text(f"Who leaves for your new {new}?", (rect.centerx, rect.y + 32), 22, INK, True, "center")
        self.text(f"You can have {g.pawn_limit(pid)} pawns. The pawn you choose plays this turn, then leaves with its VP.",
                  (rect.centerx, rect.y + 62), 14, MUTED, False, "center")
        pawns = g.dismissable(pid)
        cols = 4 if len(pawns) <= 8 else 5  # 9 pawns with a Guild Hall
        width = (rect.w - 44 - (cols - 1) * 12) // cols
        for i, pawn in enumerate(pawns):
            card = pygame.Rect(rect.x + 22 + (i % cols) * (width + 12), rect.y + 90 + (i // cols) * 142, width, 132)
            hover = card.collidepoint(self.mouse)
            draw.rect(self.canvas, (255, 248, 226) if hover else (250, 240, 218), card, border_radius=8)
            draw.rect(self.canvas, BAD if hover else MUTED, card, 2 if hover else 1, border_radius=8)
            self.draw_unit(pawn.kind, p.team, art.IDLE, int(self.clock_time * 8) + i,
                           card.x + 40, card.y + 104, 72, False, pawn.resting)
            self.text(pawn.name, (card.x + 8, card.y + 10), 13, INK, True)
            self.text(f"{g.pawn_points(pawn)} VP", (card.right - 8, card.y + 62), 14, ACCENT, True, "midright")
            self.text(self.pawn_place(pawn), (card.right - 8, card.y + 84), 12, MUTED, False, "midright")
            self.tips.append((card, (pawn.name, pawn.info["desc"])))
            self.click_zone(card, lambda u=pawn.uid: self.do_dismiss(u))
        if kind == "build":
            self.button((rect.centerx - 160, rect.bottom - 44, 210, 32), "Keep my pawns, no Peasant",
                        lambda: self.finish_build(value), size=13)
            self.button((rect.centerx + 60, rect.bottom - 44, 100, 32), "Cancel",
                        lambda: setattr(self, "modal", "build"), size=14)
        else:
            self.button((rect.centerx - 46, rect.bottom - 44, 92, 32), "Cancel",
                        lambda: setattr(self, "modal", "town"), size=14)

    def pawn_place(self, pawn):
        """Where a pawn is, in words."""
        if pawn.resting:
            return "Out this turn"
        return "At home" if pawn.location == HOME else f"In {self.game.env(pawn.location).name}"

    def do_sell(self):
        """Sell the chosen resources."""
        pid = self.game.active
        self.game.sell(pid, {r: n for r, n in self.lots.items() if n})
        self.after_town(pid)

    # ---- fights and harvest reports -----------------------------------------
    def draw_stance(self):
        """A fight is coming: choose to fight, split or retreat."""
        g = self.game
        contest = g.contest
        env = g.env(contest["env"])
        pid = g.active
        p = g.players[pid]
        self.dim()
        options = g.stance_options(pid) if not p.is_ai else []
        height = 190 + (26 if env.mob else 0) + 46 * len(contest["players"]) + 46 * len(options)
        rect = pygame.Rect(W // 2 - 300, (H - height) // 2, 600, height)
        self.panel(rect)
        self.text(env.name, (rect.centerx, rect.y + 28), 25, INK, True, "center")
        res, qty = env.prize
        self.text("Bonus prize:", (rect.centerx - 110, rect.y + 71), 17, MUTED, True, "midleft")
        self.canvas.blit(art.resource_icon(res, 34), (rect.centerx - 6, rect.y + 54))
        self.text(g.prize_text(env), (rect.centerx + 34, rect.y + 71), 19, INK, True, "midleft")
        y = rect.y + 106
        if env.mob:
            self.text(f"{env.mob[0]}: scores a die + {env.mob[1]}", (rect.centerx, y), 16, BAD, True, "center")
            y += 26
        for other in contest["players"]:
            o = g.players[other]
            power = g.strength(other, env.eid, bool(env.mob))
            dice = g.dice_count(other, env.eid)
            roll = f"best of {dice} dice" if dice > 1 else "a die"
            self.player_name(o, f"{o.name}: {roll} + {power}", (rect.x + 40, y), 15, o.color, True, "topleft")
            self.text(self.bonus_text(other, env.eid, bool(env.mob)), (rect.x + 40, y + 20), 13, MUTED)
            if other in contest["stances"]:
                stance, target = contest["stances"][other]
                self.text(self.stance_label(stance, target), (rect.right - 40, y), 14, MUTED, False, "topright")
            y += 46
        y += 12
        if p.is_ai:
            self.text(f"{p.name} is deciding...", (rect.centerx, y + 20), 17, MUTED, False, "center")
            return
        self.text(f"{p.name}, what do you do?", (rect.centerx, y + 8), 19, INK, True, "center")
        y += 38
        for stance, target, label in g.stance_options(pid):
            primary = stance == FIGHT
            self.button((rect.centerx - 170, y, 340, 40), label,
                        lambda s=stance, t=target: g.set_stance(pid, s, t), primary=primary)
            y += 46

    def stance_label(self, stance, target):
        """A stance in a few words, such as 'Fights'."""
        if stance == FIGHT:
            return "Fights"
        if stance == SPLIT:
            return "Proposes a split"
        if target is not None:
            return f"Gives to {self.game.players[target].name}"
        return "Retreats"

    def draw_dice_row(self, label, dice, strength, score, x, y, color, rolling, player=None):
        """One side's dice, strength and score in a fight."""
        if player:
            self.player_name(player, label, (x, y + 16), 16, color, True, "midleft")
        else:
            self.text(label, (x, y + 16), 16, color, True, "midleft")
        dx = x + 210
        for value in dice:
            flicker = random.Random(int(self.clock_time * 12) + dx + y)
            shown = flicker.randint(1, 6) if rolling else value
            self.canvas.blit(art.die(shown, 34), (dx, y))
            dx += 40
        if not rolling:
            self.text(f"+ {strength}  =  {score}", (dx + 8, y + 17), 19, INK, True, "midleft")

    def draw_event_dice(self, dice, x, y):
        """Dice rolled for the zone's event, with what they did."""
        if not dice:
            return y
        g = self.game
        y += 6
        rolling = self.report_time < 0.8
        for pid, name, value, ok, result in dice:
            shown = random.Random(int(self.clock_time * 12) + y).randint(1, 6) if rolling else value
            tint = (250, 246, 234) if rolling else (214, 240, 200) if ok else (246, 206, 196)
            self.canvas.blit(art.die(shown, 24, tint), (x, y))
            who = f"{g.players[pid].name}: " if pid is not None else ""
            color = g.players[pid].color if pid is not None else INK
            line = f"{who}{name} die" if rolling else f"{who}{name} die: {value}, {result}"
            self.text(line, (x + 32, y + 12), 15, color if ok or rolling else BAD, True, "midleft")
            y += 29
        return y

    def draw_report(self):
        """The harvest report of a zone: who collected what, the fight and its result."""
        g = self.game
        report = g.report
        env = g.env(report["env"])
        self.dim()
        rect = pygame.Rect(W // 2 - 310, 50, 620, 716)
        self.panel(rect)
        self.text(env.name, (rect.centerx, rect.y + 28), 25, INK, True, "center")
        y = rect.y + 58
        self.text("Normal resource collected", (rect.x + 28, y), 15, MUTED, True)
        y += 24
        for pid, res, qty, who in report["gathers"][:8]:
            player = g.players[pid]
            self.canvas.blit(art.resource_icon(res, 22), (rect.x + 30, y))
            self.player_name(player, f"{player.name}'s {who}: +{qty} {res_name(res)}", (rect.x + 60, y + 2), 15,
                             player.color, True, "topleft")
            y += 23
        before = [d for d in report.get("event_dice", []) if d[1] != "Trapped Relic"]
        after = [d for d in report.get("event_dice", []) if d[1] == "Trapped Relic"]
        y = self.draw_event_dice(before, rect.x + 30, y)
        rolling = self.report_time < FIGHT_TIME
        if report["rolls"]:
            y += 8
            title = (f"Split: each player fights the {report['mob']['name']} alone for {g.prize_text(env)}"
                     if "split_winners" in report else f"Fight for the bonus prize: {g.prize_text(env)}")
            self.text(title, (rect.x + 28, y), 15, MUTED, True)
            y += 24
            for roll in report["rolls"]:
                alone = " and " not in roll["label"]
                color = g.players[roll["pid"]].color if alone else INK
                self.draw_dice_row(roll["label"], roll["dice"], roll["strength"], roll["score"],
                                   rect.x + 30, y, color, rolling, g.players[roll["pid"]] if alone else None)
                y += 37
            mob = report["mob"]
            if mob:
                self.draw_dice_row(mob["name"], [mob["die"]], mob["strength"], mob["score"],
                                   rect.x + 30, y, BAD, rolling)
                y += 38
            self.draw_arena(env, report, rect)
        if not rolling or not report["rolls"]:
            y += 8
            y = self.para(report["text"], rect.x + 30, y, rect.w - 60, 18, INK, True)
            y = self.draw_event_dice(after, rect.x + 30, y - 4)
            for pid, res, qty in report["awards"]:
                self.canvas.blit(art.resource_icon(res, 22), (rect.x + 30, y + 2))
                self.player_name(g.players[pid], f"{g.players[pid].name}: +{qty} {res_name(res)} (bonus prize)",
                                 (rect.x + 60, y + 3), 15, g.players[pid].color, True, "topleft")
                y += 26
            for pid in dict.fromkeys(pid for pid, _ in report["wounds"]):
                names = ", ".join(who for owner, who in report["wounds"] if owner == pid)
                self.text(f"{g.players[pid].name} lost. Out next turn: {names}.",
                          (rect.x + 30, y + 2), 14, BAD, True)
                y += 22
            self.button((rect.centerx - 90, rect.bottom - 54, 180, 40), "Continue", self.acknowledge, True, True)

    def fight_sides(self, report):
        """Who appears in the fight scene, and which side won."""
        g = self.game
        sides = []
        for roll in report["rolls"]:
            if " and " in roll["label"]:
                owners = [pid for pid, (stance, _) in report["stances"].items() if stance == SPLIT]
            else:
                owners = [roll["pid"]]
            units = [(x.kind, g.players[pid].team) for pid in owners
                     for x in g.fighters(pid, report["env"])][:4]  # Raiders stay out of the fight
            sides.append({"units": units, "score": roll["score"]})
        mob = report["mob"]
        if mob:
            unit = (D.MOB_SPRITES.get(mob["name"], "mob_gnoll"), "all")
            sides.append({"units": [unit] * mob["count"], "score": mob["score"]})  # +3 shows 3 monsters
        best = max(side["score"] for side in sides)
        for side in sides:
            side["won"] = side["score"] == best
        if "split_winners" in report:  # a split against a mob: everyone who beat it stands
            for side, roll in zip(sides, report["rolls"]):
                side["won"] = roll["pid"] in report["split_winners"]
            if mob:
                sides[-1]["won"] = not report["split_winners"]
        return sides

    def draw_arena(self, env, report, rect):
        """The fight scene: both sides attack, then the losers fall."""
        area = pygame.Rect(rect.x + 26, rect.bottom - 174, rect.w - 52, 116)
        self.canvas.blit(art.environment(env.eid, area.w, area.h), area)
        draw.rect(self.canvas, TABLE_DARK, area, 2)
        t = self.report_time
        fighting = t < FIGHT_TIME
        sides = self.fight_sides(report)
        for i, side in enumerate(sides):
            center = area.x + area.w * (i + 0.5) / len(sides)
            left_half = center < area.centerx
            lunge = 22 * abs(math.sin(t * 6)) if fighting else 0
            count = len(side["units"])
            spacing = min(34, (area.w / len(sides) - 44) / max(1, count - 1)) if count > 1 else 0
            for j, (kind, team) in enumerate(side["units"]):
                x = int(center + (j - (count - 1) / 2) * spacing + (lunge if left_half else -lunge))
                ground = area.bottom - 14 - (j % 2) * 8  # staggered, so a crowd stays readable
                if fighting:
                    self.draw_unit(kind, team, art.ATTACK, int(t * 12) + j, x, ground, 56, not left_half)
                elif side["won"]:
                    self.draw_unit(kind, team, art.IDLE, int(t * 8) + j, x, ground, 56, not left_half)
                else:
                    last = art.frame_count("dead", art.IDLE) - 1 if art.units() else 0
                    self.draw_unit("dead", "all", art.IDLE, min(int((t - FIGHT_TIME) * 12), last), x, ground, 44)

    # ---- zones window -------------------------------------------------------
    def draw_zones(self):
        """Everything each zone in this game can offer."""
        g = self.game
        self.dim()
        rect = pygame.Rect(40, 12, W - 80, H - 24)
        self.panel(rect)
        self.text("Zones", (rect.x + 20, rect.y + 12), 23, INK, True)
        self.text("What each zone can give. One resource, one prize and maybe one monster are revealed each turn.",
                  (rect.x + 104, rect.y + 19), 14, MUTED)
        self.button((rect.right - 104, rect.y + 10, 90, 32), "Close", self.close_viewer, size=14)
        columns = (("Each pawn collects", 152), ("Bonus prize", 366),
                   (f"Monsters (at most {D.MAX_MOBS} at a time)", 620))
        for label, x in columns:
            self.text(label, (rect.x + x, rect.y + 52), 14, ACCENT, True)
        rows = len(g.envs) + (1 if g.event_text(TOWN) else 0)
        row_h = min(96, (rect.h - 106) // rows)
        for i, env in enumerate(g.envs):
            self.draw_zone_row(env, rect.x + 14, rect.y + 74 + i * row_h, rect.w - 28, row_h - 6, columns)
        if g.event_text(TOWN):
            self.draw_market_row(rect.x + 14, rect.y + 74 + len(g.envs) * row_h, rect.w - 28, row_h - 6)
        self.text("Odds are for each turn.",
                  (rect.centerx, rect.bottom - 16), 13, MUTED, False, "center")

    def draw_zone_row(self, env, x, y, width, height, columns):
        """One zone in the Zones window: resources, prizes, mobs and event."""
        c = self.canvas
        info = D.ENVIRONMENTS[env.eid]
        draw.rect(c, (250, 240, 218), (x, y, width, height), border_radius=8)
        cell = next(iter(self.env_cells().values()))  # same framing as on the board
        tw = round(height * cell.w / cell.h)
        tx = x + (124 - tw) // 2
        c.blit(art.environment(env.eid, tw, height), (tx, y))
        tag = pygame.Rect(tx + 3, y + height - 21, tw - 6, 18)
        draw.rect(c, TABLE_DARK, tag, border_radius=5)
        self.text(info["name"], tag.center, 11, CREAM, True, "center")
        event = self.game.event_text(env.eid)
        if event:
            self.draw_event_line(event, x + 138, y + height - 11)
        middle = y + (height - 20 if event else height) // 2
        pool = info["harvest"]
        for i, res in enumerate(dict.fromkeys(pool)):
            ix = x + columns[0][1] - 14 + i * 70
            c.blit(art.resource_icon(res, 26), (ix, middle - 13))
            odds = 100 * pool.count(res) / len(pool)
            odds = odds if (2 * odds).is_integer() else round(odds)
            self.text(f"{odds:g}%", (ix + 30, middle), 13, INK, True, "midleft")
            self.tips.append((pygame.Rect(ix, middle - 13, 70, 26), (res_name(res), "")))
        for i, (res, qty) in enumerate(info["prizes"]):
            ix = x + columns[1][1] - 14 + i * 60
            c.blit(art.resource_icon(res, 26), (ix, middle - 13))
            self.text(f"x{qty}", (ix + 30, middle), 13, INK, True, "midleft")
            self.tips.append((pygame.Rect(ix, middle - 13, 56, 26), (res_name(res), "")))
        mobs = D.zone_mobs(env.eid, len(self.game.players))
        if not mobs:
            self.text("No monsters", (x + columns[2][1] - 14, middle), 13, MUTED, False, "midleft")
        for i, (name, strength) in enumerate(mobs):
            ix = x + columns[2][1] - 14 + i * 174
            image = art.unit_frame(D.MOB_SPRITES.get(name, "mob_gnoll"), "all", art.IDLE,
                                   int(self.clock_time * 8), 38)
            if image:
                c.blit(image[0], (ix + 24 - image[1], middle + 24 - (10 if event else 0) - image[2]))
            ability = self.game.mob_abilities and D.MOB_SHORT.get(name)
            lines = ability.split("|") if ability else []
            lift = 6 * len(lines) + (2 if len(lines) > 2 else 0)
            self.text(name, (ix + 52, middle - 9 - lift), 13, INK, True, "midleft")
            self.text(f"Die + {strength}", (ix + 52, middle + 9 - lift), 13, BAD, True, "midleft")
            if ability:
                for k, line in enumerate(lines):
                    self.text(line, (ix + 52, middle + 22 - lift + 7 + k * 11), 10, MUTED, True, "midleft")
                self.tips.append((pygame.Rect(ix, middle - 26, 170, 54), (name, D.MOB_ABILITIES[name])))

    def draw_event_line(self, event, x, y):
        """An event's name and text in the Zones window."""
        self.text(f"{event[0]}:", (x, y), 13, BAD, True, "midleft")
        width = self.font(13, True).size(f"{event[0]}: ")[0]
        self.text(event[1], (x + width, y), 13, INK, False, "midleft")

    def draw_market_row(self, x, y, width, height):
        """The Market in the Zones window."""
        c = self.canvas
        g = self.game
        draw.rect(c, (250, 240, 218), (x, y, width, height), border_radius=8)
        cell = next(iter(self.env_cells().values()))  # same framing as on the board
        tw = round(height * cell.w / cell.h)
        tx = x + (124 - tw) // 2
        c.blit(art.town_tile(tw, height), (tx, y))
        tag = pygame.Rect(tx + 3, y + height - 21, tw - 6, 18)
        draw.rect(c, TABLE_DARK, tag, border_radius=5)
        self.text("Market", tag.center, 11, CREAM, True, "center")
        self.draw_event_line(g.event_text(TOWN), x + 138, y + height // 2)
        if g.hero:
            self.text(f"Everyone received a {D.PAWNS[g.hero]['name']}.", (x + 138, y + height // 2 + 20), 13, MUTED)

    # ---- choices, rules and the end of the game -----------------------------
    def draw_choice(self):
        """A player must decide something for a zone event or the Infirmary."""
        g = self.game
        c = g.choices[0]
        p = g.players[g.active]
        options = g.choice_options() if not p.is_ai else []
        self.dim()
        rect = pygame.Rect(W // 2 - 280, H // 2 - 60 - 23 * len(options), 560, 120 + 46 * len(options))
        self.panel(rect)
        place = g.env(c["env"]).name if c["env"] else "Infirmary"
        self.text(place, (rect.centerx, rect.y + 28), 23, INK, True, "center")
        self.text(f"{p.name} - {c['why']}", (rect.centerx, rect.y + 60), 15, MUTED, False, "center")
        if p.is_ai:
            self.text(f"{p.name} is choosing...", (rect.centerx, rect.y + 90), 16, MUTED, False, "center")
        for i, (value, label) in enumerate(options):
            self.button((rect.centerx - 160, rect.y + 86 + i * 46, 320, 40), label,
                        lambda v=value: g.choose(g.active, v), size=15)

    def draw_rules(self):
        """The rules window."""
        self.dim()
        rect = pygame.Rect(50, 14, W - 100, H - 28)
        self.panel(rect)
        self.text("How to play", (rect.x + 24, rect.y + 14), 24, INK, True)
        self.button((rect.right - 104, rect.y + 14, 90, 32), "Close", self.close_viewer, size=14)
        rules = RULES
        size, gap = 14, 2
        line_h = self.font(size).get_height() + gap
        column_w = (rect.w - 72) // 2
        sections = []  # (title, lines): each line is (indent, text)
        for title, body in rules:
            lines = []
            for part in body.split("\n"):
                bullet = part.startswith("\u2022 ")
                indent = self.font(size).size("\u2022 ")[0] if bullet else 0
                for k, line in enumerate(self.wrap(part, column_w - indent, size)):
                    lines.append((0 if k == 0 else indent, line))
            sections.append((title, lines))
        height = lambda section: line_h + len(section[1]) * line_h + 8
        total = sum(height(s) for s in sections)
        split, filled = len(sections), 0
        for i, section in enumerate(sections):  # the first column takes about half
            if filled + height(section) / 2 > total / 2:
                split = i
                break
            filled += height(section)
        for column, part in enumerate((sections[:split], sections[split:])):
            x, y = rect.x + 24 + column * (column_w + 24), rect.y + 58
            for title, lines in part:
                self.text(title, (x, y), 15, ACCENT, True)
                y += line_h + 1
                for indent, line in lines:
                    self.text(line, (x + indent, y), size)
                    y += line_h
                y += 8

    def skip_end(self):
        """Skip the end-of-game animation."""
        self.end_time = 1000.0

    def draw_end(self):
        """The table fades out, then the scores come in from last place to the winner."""
        g = self.game
        t = self.end_time
        fade = min(1.0, t / END_FADE)
        self.canvas.shade((0, 0, W, H), (16, 10, 6, int(205 * fade)))
        self.tips = []
        count = len(g.final)
        shown = int((t - END_FADE - END_TITLE) / END_ROW) + 1 if t >= END_FADE + END_TITLE else 0
        if shown <= 0:
            image = self.font(round(64 * self.canvas.scale), True).render("Game over", True, ACCENT_LIGHT)
            image.set_alpha(int(255 * fade))
            pygame.Surface.blit(self.canvas, image, image.get_rect(center=self.canvas.point((W // 2, H // 2))))
            self.click_zone(pygame.Rect(0, 0, W, H), self.skip_end)
            return
        rect = pygame.Rect(40, 50, W - 80, 700)
        self.panel(rect)
        top = g.final[0]
        winners = [r for r in g.final if (r["total"], r["coins"]) == (top["total"], top["coins"])]
        title = " and ".join(r["name"] for r in winners) + (" win!" if len(winners) > 1 else " wins!")
        if shown <= count:
            self.text("Final scores", (rect.centerx, rect.y + 44), 36, MUTED, True, "center")
            self.click_zone(pygame.Rect(0, 0, W, H), self.skip_end)
        else:
            self.text(title, (rect.centerx, rect.y + 44), 36, ACCENT, True, "center")
        y = rect.y + 92
        for rank, row in enumerate(g.final):
            if rank < count - shown:
                y += 104
                continue
            player = g.players[row["pid"]]
            frame = int(self.clock_time * 8) + rank
            self.draw_unit("peasant", player.team, art.IDLE, frame, rect.x + 56, y + 60, 50)
            self.player_name(player, f"{rank + 1}. {row['name']}", (rect.x + 86, y + 6), 20, player.color, True,
                             "topleft")
            self.text(f"{row['total']} VP", (rect.x + 590, y + 18), 26, INK, True, "midright")
            detail = "   ".join(f"{name} {value} VP" for name, value in row["lines"])
            detail += f"   ({row['coins']} gold counted)"
            self.text(detail, (rect.x + 86, y + 38), 14, MUTED)
            y += 104
        if shown > count:
            start = END_FADE + END_TITLE + END_ROW * count
            self.draw_vp_graph(pygame.Rect(rect.x + 660, rect.y + 130, 460, 430), (t - start) / END_GRAPH)
            self.button((rect.centerx - 110, rect.bottom - 58, 220, 42), "New game", self.back_to_menu, True, True)

    def draw_vp_graph(self, area, progress):
        """Every player's VP after each turn, with gold counted. The lines draw themselves."""
        g = self.game
        c = self.canvas
        self.text("Victory points each turn", (area.centerx, area.y - 38), 18, INK, True, "center")
        top = max(10, max(max(line) for line in g.vp_history.values()))
        step = next(s for s in (5, 10, 20, 25, 50, 100, 200, 500) if top / s <= 6)
        top = -(-top // step) * step
        turns = g.max_turns
        spot = lambda turn, vp: (area.x + area.w * turn / turns, area.bottom - area.h * vp / top)
        for vp in range(0, top + 1, step):
            y = spot(0, vp)[1]
            draw.line(c, PAPER_DARK, (area.x, y), (area.right, y), 1)
            self.text(vp, (area.x - 8, y), 13, MUTED, False, "midright")
        for turn in range(0, turns + 1, 1 if turns <= 10 else 2 if turns % 2 == 0 else 3):
            x = spot(turn, 0)[0]
            draw.line(c, MUTED, (x, area.bottom), (x, area.bottom + 4), 1)
            self.text(turn, (x, area.bottom + 14), 13, MUTED, False, "center")
        self.text("Turn", (area.centerx, area.bottom + 32), 13, MUTED, True, "center")
        reach = min(1.0, max(0.0, progress)) * turns
        for row in reversed(g.final):
            line = g.vp_history[row["pid"]]
            color = g.players[row["pid"]].color
            whole = int(reach)
            points = [spot(i, vp) for i, vp in enumerate(line[:whole + 1])]
            if whole < turns:  # the part of a turn drawn so far
                a, b = line[whole], line[whole + 1]
                points.append(spot(reach, a + (b - a) * (reach - whole)))
            if len(points) > 1:
                draw.lines(c, color, False, points, 3)
            for i, vp in enumerate(line[:whole + 1]):
                draw.circle(c, color, spot(i, vp), 4)
                self.tips.append((pygame.Rect(0, 0, 14, 14).move(spot(i, vp)[0] - 7, spot(i, vp)[1] - 7),
                                  (row["name"], f"Turn {i}: {vp} VP")))

    def back_to_menu(self):
        """Leave the game for the start screen."""
        self.tutorial = None
        self.state = "menu"
        self.page = "start"
        self.game = None
        self.modal = None

    # ---- drawing a frame ----------------------------------------------------
    def draw_tooltip(self):
        """The tooltip of whatever the mouse is over."""
        for rect, tip in reversed(self.tips):
            if rect.collidepoint(self.mouse):
                title, body = tip
                lines = self.wrap(body, 260, 13) if body else []
                width = max([self.font(14, True).size(title)[0]] + [self.font(13).size(l)[0] for l in lines]) + 20
                height = 28 + 18 * len(lines)
                x = min(self.mouse[0] + 14, W - width - 6)
                y = min(self.mouse[1] + 16, H - height - 6)
                box = pygame.Rect(x, y, width, height)
                draw.rect(self.canvas, (36, 26, 20), box, border_radius=6)
                self.text(title, (x + 10, y + 6), 14, ACCENT_LIGHT, True)
                for i, line in enumerate(lines):
                    self.text(line, (x + 10, y + 25 + i * 18), 13, CREAM)
                return

    def draw(self):
        """Draw one frame: the menu, or the board and the open window."""
        self.walked, self.walking = self.walking, []  # who walked in the last frame
        self.hot = []
        self.tips = []
        self.button_rects = {}
        if self.state == "menu":
            self.draw_menu()
        else:
            g = self.game
            self.draw_game()
            if g.phase == "end":
                self.draw_end()
            elif g.phase == "harvest" and g.harvest_stage == "stance":
                self.draw_stance()
            elif g.phase == "harvest" and g.harvest_stage == "report" and not self.no_fight():
                self.draw_report()
            elif g.phase == "harvest" and g.harvest_stage == "choice":
                self.draw_choice()
            elif self.modal == "build":
                self.draw_build()
            elif self.modal == "alchemy":
                self.draw_alchemy_modal()
            elif self.modal == "end_check":
                self.draw_end_check()
            elif self.modal == "horn":
                self.draw_horn()
            elif self.modal == "town":
                self.draw_town_modal()
            elif self.modal == "dismiss":
                self.draw_dismiss()
            if self.modal == "rules":
                self.draw_rules()
            elif self.modal == "settings":
                self.draw_settings()
            elif self.modal == "catalog":
                self.draw_build(catalog=True)
            elif self.modal == "zones":
                self.draw_zones()
            elif self.modal != "build" and (g.phase == "harvest" or self.modal == "town"):
                self.draw_top_buttons()
            self.draw_toast()
            self.draw_banner()
            if self.tutorial:
                self.tutorial.draw()
            if self.confirm_exit:
                self.draw_exit_confirm()
            self.draw_unlock()
        self.draw_tooltip()

    # ---- window scaling -----------------------------------------------------
    def fit(self, size):
        """Draw at the full resolution of the screen, centered, without stretching."""
        scale = min(size[0] / W, size[1] / H)
        picture = (round(W * scale), round(H * scale))
        art.set_scale(scale)
        self.words = {}
        self.canvas = Screen(picture, scale)
        self.view = ((size[0] - picture[0]) // 2, (size[1] - picture[1]) // 2, scale)
        self.pixels = size

    def present(self):
        """Show the frame, centered, at the screen's full resolution."""
        window = self.native.get_surface() if self.native else self.window
        if window.get_size() != self.pixels:
            self.fit(window.get_size())
            return
        if self.view[:2] != (0, 0):
            window.fill(BORDER)
        window.blit(self.canvas, self.view[:2])
        if self.native:
            self.native.flip()
        else:
            pygame.display.flip()

    def to_canvas(self, pos):
        """Mouse positions come in screen points, which are 2 pixels each on Retina."""
        ox, oy, scale = self.view
        density = self.pixels[0] / self.native.size[0] if self.native else 1
        return (int((pos[0] * density - ox) / scale), int((pos[1] * density - oy) / scale))

    def toggle_fullscreen(self):
        """Switch between full screen and a window that fits the screen."""
        if not self.native:
            return
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.native.set_fullscreen(True)
            return
        self.native.set_windowed()
        # a window as tall as the screen would hide its top under the title bar
        width, height = pygame.display.get_desktop_sizes()[0]
        scale = min(1, (width - 40) / W, (height - 120) / H)
        self.native.size = (int(W * scale), int(H * scale))
        self.native.position = pygame.WINDOWPOS_CENTERED


# ---- starting the program ---------------------------------------------------
def web_size():
    """In a browser, draw at the screen's real pixel density (2x on Retina, at most), so everything is
    sharp: the page then shrinks the picture to fit, instead of stretching a small one. See web_mouse
    for the clicks."""
    try:
        from platform import window  # the browser's page
        ratio = float(window.devicePixelRatio or 1)
    except Exception:
        ratio = 1.0
    ratio = max(1.0, min(2.0, round(ratio * 2) / 2))  # 1, 1.5 or 2
    return round(W * ratio), round(H * ratio)


def web_mouse(pos):
    """Where the mouse is on the board (1280 x 800), in a browser. Measured on a Mac: the browser gives
    the mouse in the page's picture pixels, whatever the size the game draws at."""
    try:
        from platform import window
        return int(pos[0] * W / float(window.canvas.width)), int(pos[1] * H / float(window.canvas.height))
    except Exception:
        return None


def open_window():
    """A full-screen window that uses every pixel of a Retina screen, if pygame can.
    It opens as a normal window and goes full screen a moment later: opened full screen
    straight away, macOS sent the clicks to the wrong place until the window was resized."""
    if WEB:
        return None  # in a browser the page holds a single 1280 x 800 canvas
    try:
        return pygame.Window("Tiny Realms", (W, H), allow_high_dpi=True, resizable=True)
    except (AttributeError, TypeError, pygame.error):
        return None


async def main():
    """Open the window and run the game loop: events, update, draw, 60 times a second.
    It is async so the browser version can hand control back to the page after each frame."""
    if WEB:
        pygame.mixer.pre_init(44100, -16, 2, 4096)  # a bigger sound buffer: no crackles when a frame is slow
    pygame.init()
    pygame.display.set_caption("Tiny Realms")
    native = open_window()
    if WEB:
        window = pygame.display.set_mode(web_size())
    else:
        window = native.get_surface() if native else pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    try:
        cursor = art.mouse_cursor()
        if cursor:
            pygame.mouse.set_cursor(cursor)
    except pygame.error:
        pass  # keep the system pointer
    app = App(window, native)
    if native:
        app.fullscreen = False
    frames = 0
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(60) / 1000
        frames += 1
        if native and frames == 20:  # about a third of a second after opening
            app.toggle_fullscreen()
        if WEB and frames == 2:  # the game is drawing: hide the loading picture of the page
            try:
                from platform import document
                document.getElementById("splash").style.display = "none"
            except Exception:
                pass
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                app.key(event.key, event.unicode)
            elif event.type == pygame.MOUSEMOTION:
                app.mouse = (WEB and web_mouse(event.pos)) or app.to_canvas(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                app.mouse = (WEB and web_mouse(event.pos)) or app.to_canvas(event.pos)
                app.click(app.mouse)
        app.update(dt)
        app.draw()
        app.present()
        await asyncio.sleep(0)  # let the browser draw the frame (does nothing on a computer)
    pygame.quit()


def run():
    """Save any crash next to the game, so it can be read after the window closes."""
    try:
        asyncio.run(main())
    except Exception:
        folder = paths.ROOT
        if getattr(sys, "frozen", False):  # the Mac or Windows app can't write inside itself
            folder = os.path.expanduser("~")
        path = os.path.join(folder, "tiny_realms_crash.log" if getattr(sys, "frozen", False) else "crash.log")
        with open(path, "w") as log:
            traceback.print_exc(file=log)
        raise


if __name__ == "__main__":
    run()
