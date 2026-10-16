"""
Benchmark script comparing sequential vs. batched vs. bounded concurrent
LLM text generation in Datrixa.

Tests real local Ollama if available, or a controlled realistic local simulation
to measure throughput, wall-clock time, duplicate rate, and record integrity.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.generation.llm_text import LLMTextGenerator
from backend.services.ollama_client import check_ollama_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_llm")

SAMPLE_COMMENTS = [
    "Package arrived two days late and the outer cardboard was dented.",
    "The lotion has a pleasant scent but left my skin feeling greasy.",
    "Extremely satisfied with the speedy delivery and pristine condition.",
    "Bottle pump was jammed on arrival and required manual fixing.",
    "Average product overall, nothing special compared to similar brands.",
]

ROW_CONTEXTS = [
    "Sentiment=Negative, Rating=1, Category=Shipping",
    "Sentiment=Neutral, Rating=3, Category=Product",
    "Sentiment=Positive, Rating=5, Category=Delivery",
    "Sentiment=Negative, Rating=2, Category=Packaging",
    "Sentiment=Neutral, Rating=3, Category=General",
    "Sentiment=Positive, Rating=5, Category=Service",
    "Sentiment=Negative, Rating=1, Category=Damaged",
    "Sentiment=Positive, Rating=4, Category=Quality",
    "Sentiment=Neutral, Rating=3, Category=Usability",
    "Sentiment=Positive, Rating=5, Category=Packaging",
]


def run_benchmark(
    *,
    count: int = 10,
    model: str = "qwen2.5:1.5b",
    ollama_url: str = "http://localhost:11434",
) -> dict[str, Any]:
    ollama_online = check_ollama_available(base_url=ollama_url)
    logger.info("Local Ollama available: %s (model: %s)", ollama_online, model)

    contexts = [ROW_CONTEXTS[i % len(ROW_CONTEXTS)] for i in range(count)]

    configurations = [
        {"name": "Sequential (batch_size=1, concurrency=1)", "batch_size": 1, "concurrency": 1},
        {"name": "Batched (batch_size=5, concurrency=1)", "batch_size": 5, "concurrency": 1},
        {"name": "Concurrent Batched (batch_size=5, concurrency=2)", "batch_size": 5, "concurrency": 2},
    ]

    results = []

    for cfg in configurations:
        logger.info("--- Running configuration: %s ---", cfg["name"])
        generator = LLMTextGenerator(
            model=model,
            ollama_url=ollama_url,
            batch_size=cfg["batch_size"],
            max_concurrency=cfg["concurrency"],
            skip_health_check=not ollama_online,
        )

        t0 = time.monotonic()
        try:
            generated = generator.generate(
                column_name="customer_feedback",
                count=count,
                sample_values=SAMPLE_COMMENTS,
                row_contexts=contexts,
            )
            duration = time.monotonic() - t0
            rec_per_sec = count / max(duration, 0.001)
            unique_count = len(set(v.casefold() for v in generated))
            dup_rate = 1.0 - (unique_count / max(len(generated), 1))

            record = {
                "config": cfg["name"],
                "batch_size": cfg["batch_size"],
                "concurrency": cfg["concurrency"],
                "count_requested": count,
                "count_generated": len(generated),
                "duration_seconds": round(duration, 3),
                "records_per_second": round(rec_per_sec, 2),
                "unique_records": unique_count,
                "duplicate_rate": round(dup_rate, 4),
                "status": "success",
                "stats": generator.last_stats,
            }
        except Exception as exc:
            duration = time.monotonic() - t0
            logger.error("Configuration failed: %s with error: %s", cfg["name"], exc)
            record = {
                "config": cfg["name"],
                "batch_size": cfg["batch_size"],
                "concurrency": cfg["concurrency"],
                "count_requested": count,
                "duration_seconds": round(duration, 3),
                "status": f"failed: {type(exc).__name__}",
            }

        results.append(record)

    output = {
        "ollama_online": ollama_online,
        "model": model,
        "total_records": count,
        "configurations": results,
    }

    print("\n" + "=" * 80)
    print(f"BENCHMARK RESULTS: {count} RECORDS (Model: {model})")
    print("=" * 80)
    print(f"{'Configuration':<45} | {'Time (s)':<10} | {'Rec/sec':<10} | {'Dup Rate':<10}")
    print("-" * 80)
    for r in results:
        if r["status"] == "success":
            print(
                f"{r['config']:<45} | {r['duration_seconds']:<10.2f} | "
                f"{r['records_per_second']:<10.2f} | {r['duplicate_rate']*100:<9.1f}%"
            )
        else:
            print(f"{r['config']:<45} | {r['duration_seconds']:<10.2f} | FAILED ({r['status']})")
    print("=" * 80 + "\n")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark LLM generation")
    parser.add_argument("--count", type=int, default=10, help="Number of rows to generate")
    parser.add_argument("--model", type=str, default="qwen2.5:1.5b", help="Ollama model name")
    args = parser.parse_args()
    run_benchmark(count=args.count, model=args.model)
