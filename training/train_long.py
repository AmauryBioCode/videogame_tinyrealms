"""Train the 12 computer players for a long time, one after the other, again and again.

    python3 train_long.py               runs until you stop it (Ctrl+C, or close the window)
    python3 train_long.py --hours 8     stops by itself after 8 hours
    python3 train_long.py --cores 8     uses 8 processor cores (default: half of them)
    python3 train_long.py --quiet       slow but cool and silent: only the Mac's small, efficient cores

The training runs at low priority, so the computer stays usable: whatever you do comes first.

Each round, one player (for example 12 turns, 3 players, with events) trains for a while on a copy,
playing against the current player itself. The copy then plays 1,000 new games against the current
player, and replaces it only if it wins more than its fair share, without getting worse against the
plain computer. Add --plain to train against the plain computer instead, as before. So stopping at any moment is safe: the files in
trained_ai only ever hold the best player found so far. What happens is written to
trained_ai/training_log.txt.
"""
import argparse
import multiprocessing
import signal
import os
import random
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))  # the training folder
ROOT = os.path.dirname(HERE)  # the game folder, with trained_ai
sys.path.insert(0, os.path.join(ROOT, "game"))

import ai  # noqa: E402
import train  # noqa: E402

GAME_TYPES = [(turns, players, events) for turns in (8, 12) for players in (2, 3, 4) for events in (False, True)]


def label(turns, players, events):
    return f"{turns} turns, {players} players" + (", events" if events else "")


def log(text):
    line = f"{time.strftime('%Y-%m-%d %H:%M')}  {text}"
    print(line, flush=True)
    with open(os.path.join(ROOT, "trained_ai", "training_log.txt"), "a") as f:
        f.write(line + "\n")


def train_one(turns, players, events, args, seed, pool):
    """Train a copy of one player, then keep it only if it beats the current one on new games."""
    current = ai.trained_path(turns, players, events)
    candidate = current.replace(".json", "_candidate.json")
    shutil.copy(current, candidate)
    command = [sys.executable, os.path.join(HERE, "train.py"), "--resume", "--out", candidate,
               "--generations", str(args.generations), "--rounds", str(args.rounds),
               "--seed", str(seed), "--turns", str(turns), "--players", str(players)]
    if events:
        command.append("--events")
    if not args.plain:
        command.append("--self-play")
    command += ["--workers", str(args.cores)]
    subprocess.run(command, cwd=HERE, check=True, stdout=subprocess.DEVNULL)

    # a new test seed each time, so no player is tuned to one test
    test_seed = 10_000_000 + seed
    workers = args.cores
    me, rival = ai.load_trained(current), ai.load_trained(candidate)
    test = lambda w, opponent, vp=False: train.measure(pool, w, opponent, turns, args.test, test_seed, workers,
                                                       players, events, vp)
    share = lambda rate: f"{rate / players * 100:.1f}%"
    name = label(turns, players, events)
    (old_plain, old_vp, _), (new_plain, new_vp, _) = test(me, train.PLAIN, True), test(rival, train.PLAIN, True)
    if args.plain:
        better = new_plain > old_plain
        result = (f"{share(old_plain)} -> {share(new_plain)} wins against the plain computer, "
                  f"average VP {old_vp:.1f} -> {new_vp:.1f}")
    else:
        # the new player against the current one: above 1.0 means it wins more
        duel, duel_new_vp, duel_old_vp = test(rival, me, True)
        better = duel > 1.0 and new_plain >= old_plain - 0.01 * players
        result = (f"wins {share(duel)} against the current player (fair share {100 / players:.0f}%), "
                  f"average VP new {duel_new_vp:.1f} vs current {duel_old_vp:.1f}, "
                  f"{share(old_plain)} -> {share(new_plain)} against the plain computer")
    if better:
        os.replace(candidate, current)
        log(f"{name}: better, kept ({result})")
    else:
        os.remove(candidate)
        log(f"{name}: not better, the current player stays ({result})")


def quiet_worker():
    """The helper processes ignore Ctrl+C: the main one stops them cleanly, without error messages."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def main():
    parser = argparse.ArgumentParser(description="Train all the Tiny Realms computer players for a long time.")
    parser.add_argument("--cores", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                        help="processor cores to use (default: half of them, so the computer stays usable)")
    parser.add_argument("--quiet", action="store_true",
                        help="Mac only: run on the small efficient cores, slow but cool and silent")
    parser.add_argument("--hours", type=float, default=0, help="stop after this many hours (0: never)")
    parser.add_argument("--generations", type=int, default=35, help="training steps for each player each round")
    parser.add_argument("--rounds", type=int, default=12, help="games for each version tried")
    parser.add_argument("--test", type=int, default=1000, help="games for each test of the new player")
    parser.add_argument("--plain", action="store_true", help="train against the plain computer instead of itself")
    parser.add_argument("--only", help="train one game type only, for example 12_3p or 8_2p_events")
    args = parser.parse_args()

    types = GAME_TYPES
    if args.only:
        types = [t for t in GAME_TYPES if f"{t[0]}_{t[1]}p" + ("_events" if t[2] else "") == args.only]
        if not types:
            parser.error(f"Unknown game type {args.only}")
    stop_at = time.time() + args.hours * 3600 if args.hours else None
    rng = random.Random()
    if args.quiet and sys.platform == "darwin" and not os.environ.get("TRAIN_QUIET"):
        # background priority: macOS keeps the work on the efficiency cores, the fans stay off
        os.environ["TRAIN_QUIET"] = "1"
        os.execvp("taskpolicy", ["taskpolicy", "-b", sys.executable] + sys.argv)
    try:
        os.nice(15)  # low priority: what you do on the computer comes first
    except OSError:
        pass
    log(f"Training started on {args.cores} of {os.cpu_count()} processor cores" + (f" for {args.hours:g} hours" if stop_at else ""))
    with multiprocessing.Pool(args.cores, initializer=quiet_worker) as pool:
        try:
            while True:
                for turns, players, events in types:
                    if stop_at and time.time() > stop_at:
                        log("Time is up, training stopped.")
                        return
                    train_one(turns, players, events, args, rng.randrange(10 ** 8), pool)
        except KeyboardInterrupt:
            log("Training stopped. The trained_ai files hold the best players found.")
        finally:
            for name in os.listdir(os.path.join(ROOT, "trained_ai")):
                if name.endswith("_candidate.json"):
                    os.remove(os.path.join(ROOT, "trained_ai", name))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
