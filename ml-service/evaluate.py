import os
import csv
import time
from PIL import Image
import recognize as R


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def rate(preds, refs, words=False):
    if words:
        errs = sum(edit_distance(p.split(), r.split()) for p, r in zip(preds, refs))
        return errs / max(1, sum(len(r.split()) for r in refs))
    errs = sum(edit_distance(p, r) for p, r in zip(preds, refs))
    return errs / max(1, sum(len(r) for r in refs))


def main():
    rows = []
    with open("dataset/labels.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            path = os.path.join("dataset", "images", r["file_name"])
            if r.get("text") and os.path.exists(path):
                rows.append((path, r["text"].strip()))
    if not rows:
        raise SystemExit("No labeled lines found in dataset/labels.csv")

    print(f"Model: {R._MODEL_NAME} | beams: {R._NUM_BEAMS} | {len(rows)} labeled lines\n", flush=True)
    refs, raw = [], []
    t0 = time.time()
    for path, text in rows:
        print(f"reading line {len(raw) + 1}/{len(rows)}...", flush=True)
        raw.append(R._recognize_line(Image.open(path).convert("RGB")).strip())
        refs.append(text)
    cleaned = [R._clean_text(p) for p in raw]

    print()
    for ref, p in zip(refs, raw):
        mark = "OK " if ref.lower() == p.lower() else "   "
        print(f"{mark}REF  {ref}\n   PRED {p}\n")

    print(f"Raw model output : CER {rate(raw, refs):.1%}   WER {rate(raw, refs, True):.1%}")
    print(f"After cleanup    : CER {rate(cleaned, refs):.1%}   WER {rate(cleaned, refs, True):.1%}")
    print(f"({(time.time() - t0) / len(rows):.1f}s per line)")

    print(f"\nCHARACTER ACCURACY: {100 - rate(raw, refs) * 100:.1f}%")
    print(f"WORD ACCURACY:      {100 - rate(raw, refs, True) * 100:.1f}%")
    exact = sum(r.lower() == p.lower() for r, p in zip(refs, raw))
    print(f"LINES EXACTLY RIGHT: {exact}/{len(refs)} ({exact / len(refs):.0%})")
    print("\nNote: the cleanup word list was built from this same page, so the "
          "'After cleanup' score is optimistic. Trust the raw score more.")


if __name__ == "__main__":
    main()