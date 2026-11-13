"""Play the whole tutorial with clicks, as a new player would."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import app as M  # noqa: E402


def play_tutorial():
    """Click through every step, as a new player would; returns the app on the last step."""
    pygame.init()
    a = M.App(pygame.Surface((M.W, M.H)))
    a.draw()
    assert "Tutorial" not in a.button_rects  # it comes after Start
    a.click(a.button_rects["Start"].center)
    a.draw()
    a.click(a.button_rects["Tutorial"].center)
    t, g = a.tutorial, a.game

    def tick(n=3):
        for _ in range(n):
            a.update(0.2)
            a.draw()

    def click(rect):
        a.click(pygame.Rect(rect).center)
        tick()

    for _ in range(600):
        tick()
        step = t.step
        if step.get("final"):
            break
        title = step["title"]
        if not step.get("done"):
            if "Next" in a.button_rects:  # AI's moves are shown before Next appears
                click(a.button_rects["Next"])
        elif title == "Step 1: Send pawns":
            click(a.env_cells()[M.TOWN])
            assert not g.pawns_at(0, M.TOWN)  # only the monster's zone is allowed
            click(a.env_cells()[t.zone.eid])
        elif title == "Challenge AI":
            click(a.env_cells()[t.duel.eid])
        elif title == "Your turn again":
            click(a.env_cells()[M.TOWN])
        elif title == "Stay home":
            click(a.button_rects["Keep pawn home"])
        elif title == "Step 2: Build and trade":
            click(a.button_rects["Build"])
        elif title == "Choose a building":
            nodes = a.tree_nodes(pygame.Rect(20, 16, M.W - 40, M.H - 32))
            click(nodes[next(b for b in nodes if g.can_build(0, b)[0])])
        elif title == "Your first building!":
            click(a.button_rects["Town"])
        elif title == "Sell":
            stock = next(r for r, n in g.players[0].res.items() if n)
            a.lots = {stock: g.players[0].res[stock]}  # as with + or All
            click(a.button_rects["Sell selected"])
        elif title == "Recruit":
            i = next(i for i in range(len(g.recruits[0])) if g.can_recruit(0, i)[0])
            click((480, 174 + i * 138, 136, 36))
        elif title == "Welcome aboard!" and "End" in a.button_rects:
            click(a.button_rects["End"])
            if a.modal == "end_check":
                click(a.button_rects["End turn"])
        elif title == "Step 3: Harvest and fight" and "Fight the mob" in a.button_rects:
            click(a.button_rects["Retreat"])
            assert g.harvest_stage == "stance"
            click(a.button_rects["Fight the mob"])
        elif title == "Victory!" and "Continue" in a.button_rects and a.report_time > M.FIGHT_TIME:
            report = g.report
            assert report["rolls"][0]["score"] > report["mob"]["score"]  # you beat the monster
            click(a.button_rects["Continue"])
        elif title == "Fight against AI" and "Fight for it" in a.button_rects:
            click(a.button_rects["Retreat"])
            assert g.harvest_stage == "stance"  # the tutorial wants a fight
            click(a.button_rects["Fight for it"])
        elif title == "The fight" and "Continue" in a.button_rects and a.report_time > M.FIGHT_TIME:
            report = g.report
            you, them = report["rolls"][0]["score"], report["rolls"][1]["score"]
            assert report["mob"] is None and you < them  # then you lose against AI
            click(a.button_rects["Continue"])
    assert t.step.get("final")
    assert len(g.players[0].buildings) == 2 and len(g.players[0].pawns) == 5
    assert any(x.resting for x in g.players[0].pawns)  # the pawn that lost is shown wounded
    ai_player = g.players[1]
    assert "quarry" in ai_player.buildings and any(x.kind == "bard" for x in ai_player.pawns)
    return a


def test_tutorial_can_be_played_to_the_end():
    a = play_tutorial()
    a.click(a.button_rects["Play a game"].center)
    assert a.state == "menu" and a.page == "mode" and a.tutorial is None


def test_finish_the_game_plays_the_last_3_turns_against_the_ai():
    import ai
    a = play_tutorial()
    g = a.game
    a.click(a.button_rects["Finish the game"].center)
    assert a.tutorial is None and a.state == "game" and g.turn == 2 and g.max_turns == 4
    for _ in range(5000):  # you play like the AI, and the app runs the AI
        if g.phase == "end":
            break
        if g.phase == "harvest" and g.harvest_stage == "report":
            g.ack_report()
        elif g.phase == "harvest" and g.harvest_stage == "next":
            g.harvest_next()
        elif g.active == 0 or g.harvest_stage in ("stance", "choice"):
            ai.play_step(g)
        else:
            a.update(1.0)
    assert g.phase == "end" and g.turn == 4
