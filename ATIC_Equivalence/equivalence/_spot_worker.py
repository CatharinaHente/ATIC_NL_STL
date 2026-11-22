"""SPOT worker: reads JSON [gold, pred] lines on stdin, writes one JSON result line each.
Started by spot_backend.SpotWorker; killed by it on timeout."""
import json
import sys
import time

import spot


def main():
    for line in sys.stdin:
        gold, pred = json.loads(line)
        try:
            t0 = time.perf_counter()
            g, p = spot.formula(gold), spot.formula(pred)
            lcc = spot.language_containment_checker()     # fresh per pair: no cross-pair caching in timings
            g_in_p = bool(lcc.contained(g, p))
            p_in_g = bool(lcc.contained(p, g))
            out = ["ok", g_in_p, p_in_g, (time.perf_counter() - t0) * 1000]
        except Exception as e:                              # parse errors etc.
            msg = str(e).strip()
            out = ["error", msg.splitlines()[0][:300] if msg else repr(e)]
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
