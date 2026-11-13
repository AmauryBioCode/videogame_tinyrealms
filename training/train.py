"""Train a computer player for Tiny Realms.

    python3 train.py                         a short session of a few minutes
    python3 train.py --generations 100       a longer one
    python3 train.py --resume                continue from the saved player
    python3 train.py --check                 only measure the saved player
    python3 train.py --turns 8               train for 8-turn games
    python3 train.py --players 3             train for 3-player games
    python3 train.py --events                train for games with zone events

How it works: the computer player's decisions depend on the numbers in
DEFAULT_WEIGHTS (ai.py). Each generation tries many small random changes to
those numbers, plays every version against the same opponents, and moves
towards the versions that did best. Every version plays every seat, so the
advantage of going first does not distort the result.

Each kind of game has its own file in the trained_ai folder, such as
trained_ai_8_3p_events.json for 8
turns, 3 players and zone events. Every file is trained on a mix of games with
and without factions, and with and without the monsters' abilities. The game loads the one that matches your
choices. To play against it, choose "Trained AI" for a player in the game's menu.
You can stop at any time with Ctrl-C; the best version so far stays saved.
"""
import argparse
import json
import multiprocessing
import signal
import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game"))

import ai  # noqa: E402
import data as D
from engine import Game

# ---- playing games ----------------------------------------------------------
PLAIN = {**ai.DEFAULT_WEIGHTS, "variety": 1.0}


def seats(players):
    """Every seat of a table, so a version plays first, second... in turn."""
    return [(players, seat) for seat in range(players)]


def play_game(brains, turns, seed, events=False):
    """Play one computer-only game and return the final results. Half the games
    give each player a faction, and half turn on the monsters' abilities, so the
    trained player learns to play with every option."""
    pick = random.Random(seed * 7 + 3)
    factions = pick.sample(list(D.FACTIONS), len(brains)) if pick.random() < 0.5 else None
    monsters = pick.random() < 0.5
    game = Game([(f"P{i}", True) for i in range(len(brains))], turns=turns, seed=seed, events=events,
                factions=factions, mob_abilities=monsters)
    game.brains = dict(enumerate(brains))
    while game.phase != "end":
        if game.phase == "harvest" and game.harvest_stage == "next":
            game.harvest_next()
        elif game.phase == "harvest" and game.harvest_stage == "report":
            game.ack_report()
        else:
            ai.play_step(game)
    return game.final


def score_games(job):
    """Play one candidate in every seat. Returns (fitness, win rate over fair share,
    its average VP, the opponents' average VP)."""
    candidate, opponents, turns, seed, rounds, table, events = job
    rng = random.Random(seed)
    fitness = wins = games = points = others = 0.0
    for _ in range(rounds):
        for players, seat in seats(table):
            brains = [rng.choice(opponents) for _ in range(players)]
            brains[seat] = candidate
            final = play_game(brains, turns, rng.randrange(10 ** 9), events)
            totals = {row["pid"]: row["total"] for row in final}
            average = sum(totals.values()) / players
            won = final[0]["pid"] == seat
            points += totals[seat]
            others += (sum(totals.values()) - totals[seat]) / (players - 1)
            wins += players if won else 0
            fitness += (players if won else 0) + 0.5 * (totals[seat] / max(1, average) - 1)
            games += 1
    return fitness / games, wins / games, points / games, others / games


# ---- evolving the numbers ---------------------------------------------------
def mutate(mean, step, rng, events=False):
    """A random variation. Each number moves in proportion to its size.
    Event numbers only change when the games have events to judge them."""
    child = dict(mean)
    for key in ai.DEFAULT_WEIGHTS:
        if key in ai.EVENT_WEIGHTS and not events:
            continue
        child[key] = max(0.0, mean[key] + rng.gauss(0, step) * max(abs(mean[key]), 0.25))
    child["variety"] = 0.0
    return child


def recombine(ranked):
    """Average the best half, giving the very best more weight."""
    best = ranked[:max(2, len(ranked) // 2)]
    shares = [len(best) - i for i in range(len(best))]
    total = sum(shares)
    mean = {k: sum(s * b[k] for s, b in zip(shares, best)) / total for k in ai.DEFAULT_WEIGHTS}
    mean["variety"] = 0.0
    return mean


# ---- saving and measuring ---------------------------------------------------
def save(path, weights, info):
    """Write the weights safely: to a temporary file first, then rename it."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w") as f:
        json.dump({"weights": {k: round(weights[k], 4) for k in ai.DEFAULT_WEIGHTS}, **info}, f, indent=2)
    os.replace(temp, path)


def measure(pool, weights, opponent, turns, rounds, seed, workers, table=2, events=False, with_vp=False):
    """Win rate over fair share against one opponent: 1.0 means no better than even.
    With with_vp, returns (win rate, average VP of the measured player, average VP of its opponents)."""
    per_job = max(1, rounds // workers)
    jobs = [(weights, [opponent], turns, seed + i, per_job, table, events) for i in range(workers)]
    results = pool.map(score_games, jobs)
    rate = sum(r[1] for r in results) / len(results)
    if not with_vp:
        return rate
    return rate, sum(r[2] for r in results) / len(results), sum(r[3] for r in results) / len(results)


# ---- the training session ---------------------------------------------------
def quiet_worker():
    """The helper processes ignore Ctrl+C: the main one stops them cleanly, without error messages."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def main():
    """Read the command line, then train generation after generation, saving the best version."""
    parser = argparse.ArgumentParser(description="Train a Tiny Realms computer player.")
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--population", type=int, default=16, help="versions tried each generation")
    parser.add_argument("--rounds", type=int, default=9, help="pairs of games per version")
    parser.add_argument("--step", type=float, default=0.25, help="size of the random changes")
    parser.add_argument("--turns", type=int, default=12, help="turns per game")
    parser.add_argument("--players", type=int, default=2, choices=(2, 3, 4), help="players per game")
    parser.add_argument("--events", action="store_true", help="play with zone events")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", help="file to save to (default: a file in the trained_ai folder)")
    parser.add_argument("--resume", action="store_true", help="continue from the saved player")
    parser.add_argument("--check", action="store_true", help="only measure the saved player")
    parser.add_argument("--self-play", action="store_true",
                        help="train against the saved player itself instead of the plain computer")
    args = parser.parse_args()

    args.out = args.out or ai.trained_path(args.turns, args.players, args.events)
    table, events = args.players, args.events
    rng = random.Random(args.seed)
    saved = ai.load_trained(args.out)
    if (args.resume or args.check) and saved is None:
        parser.error(f"No saved player in {args.out}")

    with multiprocessing.Pool(args.workers, initializer=quiet_worker) as pool:
        if args.check:
            rate = measure(pool, saved, PLAIN, args.turns, 180, 777000, args.workers, table, events)
            print(f"Saved player wins {rate:.2f} times its fair share against the plain computer.")
            return

        start = saved if args.resume else ai.load_for_turns(args.turns)  # the best we have so far
        mean = dict(start) if start else {**ai.DEFAULT_WEIGHTS, "variety": 0.0}
        rival = dict(mean) if args.self_play else PLAIN  # who the new versions must beat
        best_rate = measure(pool, mean, rival, args.turns, 90, 555000, args.workers, table, events)
        best = dict(mean)
        against = "itself" if args.self_play else "the plain computer"
        print(f"Start: {best_rate:.2f} times fair share against {against} (1.00 is even)")
        rivals = [rival]
        step = args.step
        started = time.time()
        games_played = 0
        try:
            for generation in range(1, args.generations + 1):
                seed = rng.randrange(10 ** 9)
                versions = [mutate(mean, step, rng, events) for _ in range(args.population)]
                jobs = [(v, rivals, args.turns, seed, args.rounds, table, events) for v in versions]
                results = pool.map(score_games, jobs, chunksize=1)
                games_played += len(jobs) * args.rounds * table
                order = sorted(range(len(versions)), key=lambda i: -results[i][0])
                mean = recombine([versions[i] for i in order])
                rate = measure(pool, mean, rival, args.turns, 45, 555000, args.workers, table, events)
                note = ""
                if rate > best_rate:
                    best_rate, best = rate, dict(mean)
                    save(args.out, best, {"fair_share_vs_plain": round(best_rate, 3),
                                          "generations": generation, "turns": args.turns})
                    note = "  saved"
                rivals = [rival] + rivals[1:][-2:] + [best]
                step = max(0.08, step * 0.97)
                print(f"Generation {generation:3}/{args.generations}  best in batch "
                      f"{results[order[0]][1]:.2f}  new version {rate:.2f}  "
                      f"best so far {best_rate:.2f}  {time.time() - started:5.0f}s{note}", flush=True)
        except KeyboardInterrupt:
            print("\nStopped early.")

        final = measure(pool, best, rival, args.turns, 180, 777000, args.workers, table, events)
        save(args.out, best, {"fair_share_vs_plain": round(final, 3), "turns": args.turns,
                              "players": table, "events": events, "games": games_played})
        print(f"Finished after {games_played} training games.")
        print(f"On fresh games the trained player wins {final:.2f} times its fair share "
              f"against {against}. Saved in {args.out}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
