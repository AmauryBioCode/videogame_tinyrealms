"""Every building has an image, and the game still works if an image is missing."""
import os
import sys

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game"))
pygame = pytest.importorskip("pygame")

import art
import data as D

STYLES = sorted({b["style"] for b in D.BUILDINGS.values()} | {"hall"})


@pytest.fixture(autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((10, 10))
    art._cache.clear()


@pytest.mark.parametrize("style", STYLES)
def test_every_building_has_an_image(style):
    assert os.path.exists(os.path.join(art.ASSETS, f"{style}.png"))
    assert art.building(style, (200, 0, 0), 2).get_size() == (148, 172)


def test_missing_image_falls_back_to_the_drawing(monkeypatch, tmp_path):
    monkeypatch.setattr(art, "ASSETS", str(tmp_path))
    image = art.building("farm", (200, 0, 0), 2)
    assert image.get_size() == (148, 172) and image.get_bounding_rect().width > 0


@pytest.mark.parametrize("kind", list(D.PAWNS))
def test_every_pawn_has_idle_run_and_attack(kind):
    for team in ("red", "blue", "yellow", "purple"):
        for anim in (art.IDLE, art.RUN, art.ATTACK):
            assert art.frame_count(kind, anim) >= 1
            image, _, _ = art.unit_frame(kind, team, anim, 0, 40)
            assert image.get_bounding_rect().height > 0


def test_every_resource_and_environment_has_art():
    for res in list(D.RESOURCES) + ["gold"]:
        assert art.resource_icon(res, 24).get_width() == 24
    for eid in D.ENVIRONMENTS:
        assert os.path.exists(os.path.join(art.ROOT, "environments", f"{eid}.png"))


def test_every_monster_has_its_own_sprite_not_used_by_a_pawn():
    names = {name for env in D.ENVIRONMENTS.values() for name, _ in env["mobs"]}
    assert names == set(D.MOB_SPRITES)
    for kind in set(D.MOB_SPRITES.values()):
        assert kind not in D.PAWNS
        assert art.unit_frame(kind, "all", art.ATTACK, 0, 40)[0].get_bounding_rect().height > 0


def test_mouse_cursor_comes_from_the_texture_pack():
    cursor = art.mouse_cursor()
    assert cursor is not None
    pygame.mouse.set_cursor(cursor)
