"""İzole MathAI ölçümü (TA-005B §6). Yerel makinede çalışır; sağlayıcı ve ağ çağrısı yoktur.

    python -m scripts.mathai_bench [--samples 20] [--concurrency 1 4 8] [--cpu-hogs 0 N]

Her senaryoda süreç başlatma (yorumlayıcı + içe aktarma + IPC) ve hesaplama ayrı ölçülür:
- ``ping``: yalnız başlatma (hesap yok)
- ``lesson``: bir ders isteğinin MathAI işi (uzlaştırma + doğrulama tek süreçte)
Çıktı p50/p95 milisaniyedir. Gerçek Cloud Run'da ölçülmemiştir.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor


def _hog(stop):
    while not stop.is_set():
        sum(i * i for i in range(10_000))


def _pct(values, q):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 1)


def run_case(operation, samples, concurrency):
    from apps.api.app.features.mathai.isolated import IsolatedMathAI, MathAIUnavailable
    from apps.api.tests.test_mathai import plan

    math = IsolatedMathAI(max_processes=concurrency, max_waiting=samples)
    math.queue_timeout_seconds = 120
    payload = plan().model_dump(mode="json")
    rows, errors = [], 0

    def one(_):
        nonlocal errors
        started = time.perf_counter()
        try:
            math._run(operation, payload if operation != "ping" else None)
        except MathAIUnavailable:
            errors += 1
            return None
        timing = dict(math.last_timing)
        timing["wall_ms"] = (time.perf_counter() - started) * 1000  # kuyruk beklemesi dahil
        return timing

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = [row for row in pool.map(one, range(samples)) if row]
    summary = {"errors": errors}
    for key in ("startup_ms", "compute_ms", "wall_ms"):
        values = [row[key] for row in rows]
        summary[key] = {"p50": _pct(values, 0.5), "p95": _pct(values, 0.95),
                        "mean": round(statistics.fmean(values), 1)} if values else None
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8])
    parser.add_argument("--cpu-hogs", type=int, nargs="+", default=[0, os.cpu_count() or 2])
    args = parser.parse_args(argv)
    report = {"cpu_count": os.cpu_count(), "cases": []}
    for hogs in args.cpu_hogs:
        stop = multiprocessing.Event()
        workers = [multiprocessing.Process(target=_hog, args=(stop,), daemon=True) for _ in range(hogs)]
        for worker in workers:
            worker.start()
        try:
            for operation in ("ping", "lesson"):
                for concurrency in args.concurrency:
                    result = run_case("ping" if operation == "ping" else "reconcile_verify", args.samples, concurrency)
                    report["cases"].append({"cpu_hogs": hogs, "operation": operation, "concurrency": concurrency, **result})
                    print(json.dumps(report["cases"][-1], ensure_ascii=False), flush=True)
        finally:
            stop.set()
            for worker in workers:
                worker.join()
    return report


if __name__ == "__main__":
    main()
