"""All the game content: resources, environments, mobs, pawns (PNJ) and buildings.

Edit the numbers here to rebalance the game or add new content.
"""

# ---- game settings ----------------------------------------------------------
PLAYER_COLORS = [
    ("Red", (214, 62, 58)),
    ("Blue", (58, 120, 222)),
    ("Yellow", (206, 158, 34)),
    ("Purple", (156, 84, 204)),
]

START_GOLD = 5
START_RESOURCES = {"wood": 2, "stone": 1, "food": 1}
MAX_PAWNS = 8
INTEREST_STEP, INTEREST_MAX = 5, 15
MAX_BUILDINGS = 15  # the Town Hall sits on a 16th plot
MOB_CHANCE = 0.55
MAX_MOBS = 2  # most mobs on the table
MOBS_REMOVED = {2: 0, 3: 1, 4: 2}  # strongest mobs of each zone left out, by number of players
GOLD_PER_VP = 5  # at game end
ROTATE_FIRST_PLAYER = True  # a different player starts each turn
RECRUITS_PER_TURN = 3  # random recruits, plus a Peasant who is always available

# ---- resources --------------------------------------------------------------
# name, usual price in gold, rare?
RESOURCES = {
    "wood": ("Wood", 1, False),
    "stone": ("Stone", 1, False),
    "food": ("Food", 1, False),
    "iron": ("Iron", 2, False),
    "herbs": ("Herbs", 2, False),
    "amber": ("Amber", 4, True),
    "pearl": ("Pearl", 4, True),
    "crystal": ("Crystal", 6, True),
    "mithril": ("Gemme", 6, True),
    "relic": ("Relic", 8, True),
}
RESOURCE_IDS = list(RESOURCES)
ALCHEMY = {"crystal": "amber", "mithril": "pearl"}  # result: what it is made from
# ---- mobs -------------------------------------------------------------------
# What each mob does in an advanced game. X is the mob's strength: its number of fighters.
MOB_ABILITIES = {
    "Gnolls": "If they beat you, you lose 1 gold per Gnoll.",
    "Bears": "If you beat them, you gain 1 Food.",
    "Skeletons": "If you beat them, you gain 1 Iron.",
    "Snakes": "If they beat you, one of your beaten pawns, at random, is wounded. Only the Infirmary can save it.",
    "Spiders": "If they beat you, one of your beaten pawns, at random, is caught in their web: it stays in this "
               "zone next turn. If it isn't wounded, it collects and fights there as usual.",
}
MOB_SHORT = {  # the same abilities, in a few words
    "Gnolls": "Win: -1 gold per pawn", "Bears": "Beaten: +1 Food", "Skeletons": "Beaten: +1 Iron",
    "Snakes": "Win: a random pawn|is wounded (only the|Infirmary can save it)", "Spiders": "Win: a random pawn|is stuck in this zone|next turn",
}
# ---- special pawns and market prices ----------------------------------------
MASON_RESOURCES = ("wood", "stone", "food", "iron", "herbs")  # what the Mason can halve
LAB_RESULTS = {"wood": 2, "stone": 2, "food": 2, "iron": 1}  # what the Alchemy Lab makes from 1 Herbs

# Each turn's market price is drawn from these. A price listed twice is twice
# as likely. Resources not listed always sell at their usual price.
PRICE_ODDS = {
    "amber": [3, 4, 4, 5],
    "pearl": [3, 4, 4, 5],
    "crystal": [5, 6, 6, 7],
    "mithril": [5, 6, 6, 7],
    "relic": [7, 8, 8, 9, 10],
}

# ---- zones ------------------------------------------------------------------
# harvest: the pool from which one resource is revealed each turn.
# prizes: (resource, quantity). "gold" is paid directly.
# mobs: (name, strength). A mob scores d6 + strength.
ENVIRONMENTS = {
    "forest": {
        "name": "Forest",
        "harvest": ["wood"] * 6 + ["food", "herbs"],  # 75% Wood
        "prizes": [("amber", 1), ("wood", 4), ("herbs", 2)],
        "mobs": [("Bears", 2), ("Gnolls", 3), ("Skeletons", 5)],
    },
    "mountain": {
        "name": "Mountain",
        "harvest": ["stone", "stone", "iron"],
        "prizes": [("crystal", 1), ("iron", 2), ("mithril", 1)],
        "mobs": [("Gnolls", 3), ("Snakes", 4), ("Skeletons", 6)],
    },
    "lake": {
        "name": "Lake",
        "harvest": ["food", "food", "herbs", "wood"],
        "prizes": [("pearl", 1), ("pearl", 2), ("food", 4)],
        "mobs": [("Spiders", 2), ("Gnolls", 4)],
    },
    "mine": {
        "name": "Old Mine",
        "harvest": ["iron", "iron", "stone"],
        "prizes": [("crystal", 1), ("gold", 5), ("iron", 2)],
        "mobs": [("Snakes", 2), ("Spiders", 3), ("Gnolls", 5)],
    },
    "swamp": {
        "name": "Swamp",
        "harvest": ["herbs", "herbs", "food", "wood"],
        "prizes": [("amber", 2), ("herbs", 2), ("pearl", 1)],
        "mobs": [("Spiders", 1), ("Bears", 4), ("Skeletons", 6)],
    },
    "ruins": {
        "name": "Ancient Ruins",
        "harvest": ["stone", "iron", "herbs"],
        "prizes": [("relic", 1), ("gold", 8), ("crystal", 1), ("mithril", 1)],
        "mobs": [("Snakes", 3), ("Gnolls", 5), ("Skeletons", 7)],
    },
    "plains": {
        "name": "Plains",
        "harvest": ["food", "wood", "stone"],
        "prizes": [("gold", 3), ("food", 3), ("wood", 3), ("stone", 3)],
        "mobs": [("Bears", 1), ("Snakes", 3)],
    },
}

MOB_SPRITES = {
    "Bears": "mob_bear", "Gnolls": "mob_gnoll", "Skeletons": "mob_skull",
    "Snakes": "mob_snake", "Spiders": "mob_spider",
}

# ---- zone events (advanced game) --------------------------------------------
# Optional zone events: each zone keeps one for the whole game.
# zone: {key: (name, what it does)}. "town" is the Market.
ZONE_EVENTS = {
    "forest": {
        "wild_berries": ("Wild Berries", "Each player who collects Wood here also gains +1 Food."),
        "forest_fire": ("Forest Fire", "Each turn, a die is rolled: on a 1, each player here chooses one pawn that comes back wounded."),
        "sacred_grove": ("Sacred Grove", "Each player who sent exactly one pawn here gains +1 Wood."),
        "territorial_animals": ("Territorial Animals", "Each player with more than 2 pawns here leaves one behind: it misses next turn."),
    },
    "mountain": {
        "high_ground": ("High Ground", "Each pawn has +1 in fights here."),
        "avalanche": ("Avalanche", "Each turn, a die is rolled: on a 1, each player here chooses one pawn that comes back wounded."),
        "crystal_caves": ("Crystal Caves", "Each player who collects Iron here also gains +1 Stone."),
        "narrow_pass": ("Narrow Pass", "Only the first 2 pawns each player places here count in fights."),
        "mountain_shrine": ("Mountain Shrine", "The winner of a fight here, even against a monster, gains +2 gold."),
    },
    "lake": {
        "good_fishing": ("Good Fishing", "Each player who collects Food here gains +1 Food."),
        "abundance": ("Abundance", "Each turn, a die is rolled: on 4, 5 or 6, +1 Food is added to the bonus prize."),
        "golden_fish": ("Golden Fish", "Each player who collects Food here rolls a die. On a 6, they gain +2 gold."),
        "deep_waters": ("Deep Waters", "Players with at least 2 pawns here gain +2 Food if they collect Food (not the bonus prize)."),
    },
    "mine": {
        "ancient_machinery": ("Ancient Machinery", "Each player who collects Iron here also gains +1 Stone."),
        "gold_nugget": ("Gold Nugget", "Each player who collects here rolls a die. On a 6, they gain +3 gold."),
        "rich_iron_vein": ("Rich Iron Vein", "Each player with a pawn here gains +1 Iron."),
        "rich_stone_vein": ("Rich Stone Vein", "Each player with a pawn here gains +1 Stone."),
        "prospectors_claim": ("Prospector's Claim", "The player with the most pawns here gains +1 Iron. Nobody gains it on a tie."),
    },
    "swamp": {
        "healing_mud": ("Healing Mud", "Pawns here can't be wounded."),
        "fog": ("Fog", "Nobody can see if there is a monster until all pawns are placed."),
        "sunken_treasure": ("Sunken Treasure", "Whoever wins the bonus prize here also gains +2 gold."),
        "swamp_gas": ("Swamp Gas", "Each pawn has -1 in fights here, but always counts for at least 1."),
        "quicksand": ("Quicksand", "Each player can place at most 2 pawns here."),
        "plague": ("Plague", "Each turn, a die is rolled: on a 1, each player here chooses one pawn that comes back wounded."),
    },
    "town": {
        "traveling_merchant": ("Traveling Merchant", "The first Relic sold in the game is worth 12 gold."),
        "market_tax": ("Market Tax", "Each sale pays 2 gold less (minimum 0)."),
        "holy_grail": ("Holy Grail", "Relics always sell for 10 gold."),
        "wandering_hero": ("Wandering Hero", "At the start of the game, every player receives the same free pawn."),
    },
    "ruins": {
        "curse": ("Curse", "Whoever wins the bonus prize here loses 1 gold, if they have any."),
        "trapped_relic": ("Trapped Relic", "When the bonus prize is won here, roll a die. On a 1, it is lost."),
        "forgotten_treasury": ("Forgotten Treasury", "Whoever wins the bonus prize here also gains +2 gold."),
        "ancient_knowledge": ("Ancient Knowledge", "The first player to place a pawn here each turn has +1 in fights here."),
        "cursed_treasure": ("Cursed Treasure", "Whoever wins the bonus prize chooses: lose 2 gold or send one pawn back wounded."),
    },
    "plains": {
        "good_harvest": ("Good Harvest", "Each player who collects Food or Wood here gains +1 more."),
        "fertile_fields": ("Fertile Fields", "Players with exactly 1 pawn here gain +2 Food if they collect Food (not the bonus prize)."),
        "open_ground": ("Open Ground", "Buildings give no fight bonus here."),
        "trade_route": ("Trade Route", "The first player to place a pawn here each turn gains +1 gold."),
        "migrating_herds": ("Migrating Herds", "Each turn, a die is rolled: on 5 or 6, +1 Food is added to the bonus prize."),
        "friendly_monster": ("Friendly Monster", "A monster here joins the first player to place a pawn, for this turn's fight. It collects nothing."),
    },
}
RARE_DISASTERS = ("forest_fire", "avalanche", "plague")  # at most one per game

# ---- pawns ------------------------------------------------------------------
# Abilities are data. The rules engine reads these keys:
#   combat       bonus in every fight
#   vs_mob       extra bonus against mobs
#   harvest      resources this pawn collects one extra of
#   tough        can never be wounded
#   healer       protects your pawns in the same environment from wounds
#   extra_die    roll one more die and keep the best
#   thief        steals 1 unit of a prize of 2 or more if you lose to another player
#   diplomat     +2 gold on a split; each foe or mob fighting in its place gets -1,
#                whether or not its owner stays in the fight
#   prize_bonus  +1 unit of the prize when you win it
#   sale_bonus   gold added to a sale made by this pawn
#   recruit_discount / build_discount   cheaper recruit or building
#   half_build             at home: one building costs half of a chosen resource
#   idle_gold    gold if this pawn stays home and does not build
#   town_gold    gold if this pawn ends the action phase in town
#   alchemist    at home, instead of building, turns Amber into Crystal or Pearl into Gemme
#   vp           victory points, when not simply set by the pawn's cost
PAWNS = {
    "peasant": {"name": "Peasant", "cost": 3, "mark": "", "desc": "No ability."},
    "lumberjack": {"name": "Lumberjack", "cost": 5, "mark": "axe", "harvest": ["wood"],
                   "desc": "Collects +1 when collecting Wood."},
    "farmer": {"name": "Hunter", "cost": 4, "mark": "straw", "harvest": ["food"],
               "desc": "Collects +1 when collecting Food."},
    "miner": {"name": "Miner", "cost": 6, "mark": "helmet", "harvest": ["stone", "iron"],
              "desc": "Collects +1 when collecting Stone or Iron."},
    "herbalist": {"name": "Herbalist", "cost": 6, "mark": "leaf", "harvest": ["herbs"],
                  "desc": "Collects +1 when collecting Herbs."},
    "warrior": {"name": "Warrior", "cost": 6, "mark": "sword", "combat": 2,
                "desc": "+2 in every fight."},
    "archer": {"name": "Archer", "cost": 6, "mark": "bow", "combat": 1, "vs_mob": 2,
               "desc": "+1 in fight, additional +2 if a mob is in the fight."},
    "knight": {"name": "Lancer", "cost": 10, "mark": "shield", "combat": 3, "tough": True,
               "desc": "+3 in every fight. Never wounded."},
    "mage": {"name": "Dark Mage", "cost": 9, "mark": "wizard", "combat": 1, "extra_die": True,
             "desc": "+1 in fights. Roll an extra die and keep the best."},
    "healer": {"name": "Healer", "cost": 7, "mark": "cross", "healer": True, "combat": 1,
               "desc": "+1 in every fight. Your pawns in the same environment cannot be wounded."},
    "thief": {"name": "Thief", "cost": 7, "mark": "hood", "thief": True, "tough": True,
              "desc": "If another player beats you and the prize has 2 or more units, steal 1 unit. Never wounded."},
    "merchant": {"name": "Merchant", "cost": 9, "mark": "coin", "sale_each": 1,
                 "recruit_discount": 1,
                 "desc": "In town: +1 gold for each resource sold (no max), recruits cost 1 less."},
    "mason": {"name": "Mason", "cost": 7, "mark": "hammer", "half_build": True,
              "desc": "At home, once per turn: choose a resource in the Build window. Your next building "
                      "costs half of it, rounded up, whoever builds it. Not on the turn it is recruited."},
    "alchemist": {"name": "Goblin Alchemist", "cost": 7, "mark": "flask", "alchemist": True,
                  "desc": "At home: can build, and also turns 1 Amber into 1 Crystal, or 1 Pearl into 1 Gemme."},
    "monk": {"name": "Goblin Brewer", "cost": 6, "mark": "halo", "idle_gold": 2,
             "desc": "If idle at home: earns 2 gold."},
    "bard": {"name": "Porter", "cost": 5, "mark": "note", "town_gold": 2,
             "desc": "In town at the end of the action phase: earns 2 gold."},
    "treasure_hunter": {"name": "Treasure Hunter", "cost": 9, "mark": "map", "prize_bonus": 1,
                        "desc": "Winning a prize gives +1 unit."},
    "beast_tamer": {"name": "War Ram", "cost": 9, "mark": "paw", "combat": 1, "vs_mob": 1, "win_vp": 1,
                    "desc": "+1 in fight, additional +1 if a mob is in the fight. +1 VP per fight won."},
    "noble": {"name": "Noble", "cost": 9, "mark": "crown", "vp": 4, "combat": 1,
              "desc": "+1 in every fight. Worth 4 VP at the end of the game."},
    "champion": {"name": "Black Knight", "cost": 14, "mark": "star", "combat": 4, "tough": True,
                 "desc": "+4 in every fight. Never wounded."},
}
# ---- factions ---------------------------------------------------------------
# Starting pawns of each faction: free, worth 0 VP, never offered in town.
FACTION_PAWNS = {
    "oar_shark": {"name": "Oar Shark", "cost": 0, "vp": 2, "mark": "", "combat": 2, "tough": True,
                  "desc": "Starting pawn. +2 in fights. Never wounded."},
    "reef_hunter": {"name": "Reef Hunter", "cost": 0, "vp": 1, "mark": "", "harvest": ["wood", "food"], "harvest_bonus": 1,
                    "desc": "Starting pawn. Collects +1 when collecting Wood or Food."},
    "skull_shaman": {"name": "Skull Shaman", "cost": 0, "vp": 2, "mark": "", "shaman": 2,
                     "desc": "Starting pawn. At home, once per turn: turn 1 or 2 basic resources (Wood, Stone, "
                             "Food) into other basic resources. It can still build."},
    "spearman": {"name": "Spearman", "cost": 0, "vp": 1, "mark": "", "no_strength": True,
                 "desc": "Starting pawn. Fights for the bonus prize, but adds nothing to the fight strength."},
    "raider": {"name": "Raider", "cost": 0, "vp": 0, "mark": "", "no_bonus": True,
               "desc": "Starting pawn. Collects the zone's resource, but never fights for the bonus prize "
                       "and can't win it."},
    "dwarf_builder": {"name": "Dwarf Builder", "cost": 0, "vp": 2, "mark": "", "trim_build": True,
                      "desc": "Starting pawn. At home, once per turn: your next building costs 1 less Wood, "
                              "Stone or Food."},
    "horn_blower": {"name": "Stone Slinger", "cost": 0, "vp": 1, "mark": "", "horn": True,
                    "desc": "Starting pawn. Once per turn: choose one zone next to its own. Your pawns there get "
                            "+1 in the fight, but the Stone Slinger then adds nothing to its own fight."},
    "stone_bull": {"name": "Smashhorn", "cost": 0, "vp": 1, "mark": "", "harvest": ["stone"], "harvest_bonus": 2,
                   "desc": "Starting pawn. Collects +2 when collecting Stone."},
    "panda": {"name": "Panda Master", "cost": 0, "vp": 2, "mark": "", "extra_die": True, "tough": True, "combat": 1,
              "desc": "Starting pawn. +1 in fights. Rolls 2 dice in fights and keeps the best. Never wounded."},
}
FACTIONS = {
    # from the easiest to the hardest: the menu shows them in this order
    "beasts": {"name": "Wild Beasts", "pawns": ["stone_bull", "panda"], "difficulty": 1},
    "tidefolk": {"name": "Tidefolk", "pawns": ["oar_shark", "reef_hunter"], "difficulty": 2},
    "goblins": {"name": "Grimtooth Goblins", "pawns": ["skull_shaman", "spearman", "raider"], "difficulty": 3},
    "dwarves": {"name": "Stonebeard Dwarves", "pawns": ["dwarf_builder", "horn_blower"], "difficulty": 3},
}
DIFFICULTY_NAMES = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Very hard", 5: "Expert"}  # out of 5 stars
BASIC_RESOURCES = ("wood", "stone", "food")  # what the Skull Shaman and Dwarf Builder work with
RECRUIT_POOL = [k for k in PAWNS if k != "peasant"]
PAWNS.update(FACTION_PAWNS)

# ---- the board --------------------------------------------------------------
# Where zones go on the 3 x 3 board, beside the Town first. The Town is in the middle.
BOARD_SPOTS = [(0, 1), (2, 1), (0, 0), (2, 0), (1, 0), (0, 2), (2, 2)]
TOWN_SPOT = (1, 1)

# ---- buildings --------------------------------------------------------------
# style sets how the building is drawn in art.py.
# Effect keys read by the engine:
#   produce {resource: n}  at dawn     | gold_per_turn  at dawn
#   interest               +1 gold per INTEREST_STEP held at dawn, up to INTEREST_MAX
#   pawn_slots             more pawns allowed
#   sale_bonus             gold per sale
#   full_leftovers         unsold resources worth full base price at the end
#   combat / vs_mob / vs_player   fight bonuses
#   peasant_combat         each Peasant in a fight gives +1 more
#   no_wounds              no wounds from zone events; one pawn healed at the end of each turn
#   free_peasant           one Peasant when built
#   recruit_discount / build_discount
#   town_bonus             first town pawn acts twice each turn
#   extra_die              roll an extra die and keep the best
#   herb_lab               each turn a pawn at home can turn 1 Herbs into something else
#   mob_prize              +1 unit on prizes won against a mob
#   vp                     victory points at game end. Always worth more than
#                          selling the building's materials at their top price.
#   requires               buildings you must own first
#   requires_any           you must own at least one of these first
#   tier                   column in the building tree, and value at game end
BUILDINGS = {
    # Tier 1: no requirement
    "farm": {"name": "Farm", "tier": 1, "vp": 4, "cost": {"wood": 2}, "max": 1, "style": "farm",
             "produce": {"food": 1}, "desc": "+1 Food each turn."},
    "lumber_camp": {"name": "Lumber Camp", "tier": 1, "vp": 4, "cost": {"stone": 1, "food": 1}, "max": 1, "style": "camp",
                    "produce": {"wood": 1}, "desc": "+1 Wood each turn."},
    "quarry": {"name": "Quarry", "tier": 1, "vp": 4, "cost": {"wood": 2, "food": 1}, "max": 1, "style": "quarry",
               "produce": {"stone": 1}, "desc": "+1 Stone each turn."},
    # Tier 2
    "herb_garden": {"name": "Herb Garden", "tier": 2, "vp": 7, "requires": ["farm"], "cost": {"wood": 2, "food": 3},
                    "max": 1, "style": "garden", "produce": {"herbs": 1}, "desc": "+1 Herbs each turn."},
    "house": {"name": "House", "tier": 2, "vp": 7, "requires": ["farm"], "cost": {"wood": 3, "stone": 2, "food": 2},
              "max": 1, "style": "house", "free_peasant": True, "desc": "A free Peasant joins you when built."},
    "tavern": {"name": "Tavern", "tier": 2, "vp": 7, "requires": ["farm"], "cost": {"wood": 3, "food": 3}, "max": 1,
               "style": "tavern", "recruit_discount": 1, "desc": "Recruits cost 1 gold less."},
    "warehouse": {"name": "Warehouse", "tier": 2, "vp": 7, "requires": ["lumber_camp"], "cost": {"wood": 4, "stone": 3},
                  "max": 1, "style": "warehouse", "full_leftovers": True,
                  "desc": "At game end, unsold resources pay full price."},
    "market_stall": {"name": "Market Stall", "tier": 2, "vp": 7, "requires": ["lumber_camp"], "cost": {"wood": 4, "food": 2},
                     "max": 1, "style": "stall", "sale_bonus": 2, "desc": "+2 gold on every sale."},
    "watchtower": {"name": "Watchtower", "tier": 2, "vp": 7, "requires": ["lumber_camp"], "cost": {"wood": 3, "stone": 3},
                   "max": 1, "style": "tower", "vs_mob": 1, "desc": "+1 against mobs."},
    "iron_mine": {"name": "Iron Mine", "tier": 2, "vp": 7, "requires": ["quarry"], "cost": {"wood": 3, "stone": 3},
                  "max": 1, "style": "mine", "produce": {"iron": 1}, "desc": "+1 Iron each turn."},
    "training_ground": {"name": "Training Ground", "tier": 2, "vp": 7, "requires": ["quarry"],
                        "cost": {"wood": 3, "food": 3}, "max": 1, "style": "training", "peasant_combat": 1,
                        "desc": "Each Peasant gives +1 more in fights."},
    # Tier 3
    "infirmary": {"name": "Infirmary", "tier": 3, "vp": 10, "requires": ["herb_garden"], "cost": {"wood": 3, "herbs": 3},
                  "max": 1, "style": "infirmary", "no_wounds": True, "desc": "At the end of each turn, choose one wounded pawn: it is not wounded."},
    "alchemy_lab": {"name": "Alchemy Lab", "tier": 3, "vp": 10, "requires": ["herb_garden"],
                    "cost": {"stone": 3, "iron": 2, "herbs": 3}, "max": 1, "style": "lab", "herb_lab": True,
                    "desc": "Each turn, a pawn at home can build and also turn 1 Herbs into 2 Wood, 2 Stone, 2 Food or 1 Iron."},
    "library": {"name": "Library", "tier": 3, "vp": 9, "requires": ["house"], "cost": {"wood": 3, "stone": 2, "herbs": 3},
                "max": 1, "style": "library", "extra_die": True, "desc": "Roll an extra die in fights, keep the best."},
    "caravan_post": {"name": "Caravan Post", "tier": 3, "vp": 9, "requires": ["tavern"],
                     "cost": {"wood": 4, "food": 3, "iron": 1}, "max": 1, "style": "caravan", "town_bonus": True,
                     "desc": "One extra recruit in town each turn."},
    "workshop": {"name": "Workshop", "tier": 3, "vp": 9, "requires": ["warehouse"], "cost": {"wood": 4, "iron": 3}, "max": 1,
                 "style": "workshop", "half_build": True,
                 "desc": "Once per turn: choose a resource in the Build window. Your next building costs half of it, rounded up."},
    "statue": {"name": "Golden Statue", "tier": 3, "vp": 13, "requires": ["market_stall"], "cost": {"stone": 4, "iron": 3},
               "max": 1, "style": "statue", "desc": "A monument. Its value is all in its VP."},
    "armory": {"name": "Armory", "tier": 3, "vp": 11, "requires": ["watchtower"], "cost": {"iron": 4, "stone": 2}, "max": 1,
               "style": "armory", "vs_player": 2, "desc": "+2 in fights against players."},
    "gold_mine": {"name": "Gold Mine", "tier": 3, "vp": 11, "requires": ["iron_mine"],
                  "cost": {"wood": 3, "stone": 4, "iron": 3}, "max": 1, "style": "goldmine", "gold_per_turn": 2,
                  "desc": "+2 gold each turn."},
    "barracks": {"name": "Barracks", "tier": 3, "vp": 9, "requires": ["training_ground"],
                 "cost": {"wood": 3, "stone": 3, "iron": 2}, "max": 1, "style": "barracks", "combat": 1,
                 "desc": "+1 in every fight."},
    # Tier 4
    "temple": {"name": "Temple", "tier": 4, "vp": 23, "requires": ["library"], "cost": {"stone": 4, "iron": 2, "pearl": 1},
               "max": 1, "style": "temple", "desc": "A monument. Its value is all in its VP."},
    "guild_hall": {"name": "Guild Hall", "tier": 4, "vp": 17, "requires_any": ["caravan_post", "workshop"],
                   "cost": {"stone": 3, "iron": 4, "amber": 1}, "max": 1, "style": "guild", "pawn_slots": 1,
                   "desc": "+1 place for a pawn: you can have 9 pawns."},
    "bank": {"name": "Bank", "tier": 4, "vp": 14, "requires": ["statue"], "cost": {"stone": 4, "iron": 2, "crystal": 1},
             "max": 1, "style": "bank", "interest": True, "desc": "+1 gold per 5 gold held each turn (max 15)."},
    "trophy_hall": {"name": "Trophy Hall", "tier": 4, "vp": 17, "requires": ["barracks"],
                    "cost": {"stone": 3, "iron": 3, "amber": 1}, "max": 1, "style": "trophy", "mob_prize": 1,
                    "desc": "+1 unit on prizes won against a mob."},
    # Tier 5: the top of the tree
    "castle": {"name": "Castle", "tier": 5, "vp": 33, "requires_any": ["temple", "guild_hall", "bank", "trophy_hall"],
               "cost": {"stone": 7, "iron": 4, "crystal": 1, "mithril": 1}, "max": 1, "style": "castle",
               "desc": "The top of the tree, worth the most VP."},
}


# ---- helpers ----------------------------------------------------------------
def requirements(building):
    """Every building linked to this one in the tree."""
    info = BUILDINGS[building]
    return info.get("requires", []) + info.get("requires_any", [])


def pawn_vp(kind):
    """Peasants give 0 VP. Other pawns give 1 to 3, depending on their cost."""
    info = PAWNS[kind]
    if kind == "peasant":
        return 0
    if "vp" in info:
        return info["vp"]
    return 1 if info["cost"] <= 6 else 2 if info["cost"] <= 9 else 3


def zone_count(players):
    """How many zones are on the table."""
    return 5 if players == 2 else len(ENVIRONMENTS)


def zone_mobs(zone, players):
    """The mobs that can appear in a zone with this number of players."""
    mobs = sorted(ENVIRONMENTS[zone]["mobs"], key=lambda mob: mob[1])
    return mobs[:len(mobs) - MOBS_REMOVED.get(players, 0)]


def building_vp(building):
    """The victory points a building is worth."""
    return BUILDINGS[building]["vp"]


def top_price(resource):
    """The highest price a resource can ever sell for."""
    return max(PRICE_ODDS.get(resource, [RESOURCES[resource][1]]))
