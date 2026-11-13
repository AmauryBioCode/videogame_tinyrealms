"""Tune the Advanced AI for every kind of game (8 or 12 turns, 2 to 4 players, with or without events).

    python3 training/tune_advanced.py              all 12 kinds of game, one after the other
    python3 training/tune_advanced.py --cores 8    use 8 processor cores (default: half of them)
    python3 training/tune_advanced.py --quiet      Mac: only the small efficient cores, cool and silent
    python3 training/tune_advanced.py --only 12_3p one kind of game only

The Advanced AI plays with the Standard AI's trained numbers and looks ahead before each move: it tries
each move on a few possible futures and changes its mind when another move is worth enough more VP.
How many futures and how many VP are best can differ with the number of players, turns and events.
For each kind of game, every setting below plays against the Standard AI; the best few then play many
more games, and the winner is saved in trained_ai/advanced_ai.json, which the game reads.
The Standard AI itself is never changed. Kinds already tuned are skipped, so stopping is safe:
run it again to go on. Use --again to tune them all again. Results go to trained_ai/advanced_log.txt.
"""
import argparse
import json
import multiprocessing
import os
import signal
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "game"))
sys.path.insert(0, HERE)

import ai  # noqa: E402
import train  # noqa: E402

GAME_TYPES = [(turns, players, events) for players in (2, 3, 4) for turns in (12, 8) for events in (False, True)]
CANDIDATES = [(f, m) for f in (2, 4, 6) for m in (3, 6, 9)]  # (futures, VP margin)
DEFAULT = (4, 6)


def log(text):
    line = f"{time.strftime('%Y-%m-%d %H:%M')}  {text}"
    print(line, flush=True)
    with open(os.path.join(ROOT, "trained_ai", "advanced_log.txt"), "a") as f:
        f.write(line + "\n")


def win_share(pool, args, kind, setting, games, seed):
    """The Advanced AI with this setting in one seat, Standard AIs in the others: its share of wins in %."""
    turns, players, events = kind
    standard = ai.load_for(turns, players, events)
    futures, margin = setting
    advanced = ai.hard_brain(standard, futures, margin)
    rounds = max(args.cores, games // players)  # each round plays one game in every seat
    rate, vp, other = train.measure(pool, advanced, standard, turns, rounds, seed, args.cores, players, events, True)
    return rate / players * 100, vp, other


def tune(pool, args, kind, results):
    key = ai.game_key(*kind)
    turns, players, events = kind
    fair = 100 / players
    seed = 20_000_000 + zlib.crc32(key.encode()) % 1_000_000
    log(f"{key}: trying {len(CANDIDATES)} settings, {args.first} games each (fair share {fair:.0f}%)")
    first = {}
    for setting in CANDIDATES:
        first[setting] = win_share(pool, args, kind, setting, args.first, seed)
        log(f"  {setting[0]} futures, {setting[1]} VP: {first[setting][0]:.1f}% wins")
    best = sorted(first, key=lambda s: -first[s][0])[:args.finalists]
    if DEFAULT not in best:
        best.append(DEFAULT)  # the current setting is always in the final
    log(f"{key}: final between {', '.join(f'{f}/{m}' for f, m in best)}, {args.final} more games each")
    final = {}
    for setting in best:
        share, vp, other = win_share(pool, args, kind, setting, args.final, seed + 7)
        final[setting] = share
        log(f"  {setting[0]} futures, {setting[1]} VP: {share:.1f}% wins, average VP {vp:.1f} vs {other:.1f}")
    winner = max(final, key=final.get)
    if final[winner] < final[DEFAULT] + args.keep_default:  # not clearly better: keep the tested default
        winner = DEFAULT
    results[key] = {"settings": {"futures": winner[0], "margin": winner[1]}, "win_share": round(final[winner], 1),
                    "fair_share": round(fair, 1), "date": time.strftime("%Y-%m-%d")}
    with open(ai.ADVANCED_FILE, "w") as f:
        json.dump(results, f, indent=1)
    log(f"{key}: kept {winner[0]} futures and {winner[1]} VP ({final[winner]:.1f}% wins, fair share {fair:.0f}%)")


def quiet_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def main():
    parser = argparse.ArgumentParser(description="Tune the Tiny Realms Advanced AI for every kind of game.")
    parser.add_argument("--cores", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--quiet", action="store_true", help="Mac only: the small efficient cores, cool and silent")
    parser.add_argument("--first", type=int, default=120, help="games for each setting in the first round")
    parser.add_argument("--finalists", type=int, default=3, help="settings that go to the final")
    parser.add_argument("--final", type=int, default=400, help="games for each setting in the final")
    parser.add_argument("--keep-default", type=float, default=1.0,
                        help="another setting must win this many %% more than 4/6 to replace it")
    parser.add_argument("--only", help="one kind of game only, for example 12_3p or 8_2p_events")
    parser.add_argument("--again", action="store_true", help="tune again the kinds already tuned")
    args = parser.parse_args()
    if args.quiet and sys.platform == "darwin" and not os.environ.get("TUNE_QUIET"):
        os.environ["TUNE_QUIET"] = "1"
        os.execvp("taskpolicy", ["taskpolicy", "-b", sys.executable] + sys.argv)
    try:
        os.nice(15)  # low priority: what you do on the computer comes first
    except OSError:
        pass
    kinds = [k for k in GAME_TYPES if not args.only or ai.game_key(*k) == args.only]
    if not kinds:
        parser.error(f"Unknown kind of game {args.only}")
    try:
        with open(ai.ADVANCED_FILE) as f:
            results = json.load(f)
    except (OSError, ValueError):
        results = {}
    log(f"Tuning the Advanced AI on {args.cores} of {os.cpu_count()} processor cores")
    with multiprocessing.Pool(args.cores, initializer=quiet_worker) as pool:
        try:
            for kind in kinds:
                if ai.game_key(*kind) in results and not args.again:
                    continue
                tune(pool, args, kind, results)
            log("Done: every kind of game is tuned.")
        except KeyboardInterrupt:
            log("Stopped. The kinds already tuned are saved; run it again to go on.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
