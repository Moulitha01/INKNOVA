"""
Fine-tune TrOCR on your labeled line crops and report accuracy BEFORE vs AFTER
on pages the model never trained on.

Data (from make_dataset.py + label.html):
    dataset/images/*.png
    dataset/labels.csv        columns: file_name,text

Run on a GPU (Google Colab is fine):
    python train_trocr.py --data dataset
Output: ./trocr-finetuned  (only saved if it beats the original model)
"""

import os
import csv
import random
import argparse
import torch
from PIL import Image, ImageEnhance
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

MAX_LEN = 64


# ---------- metrics ----------
def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(preds, refs):
    errs = sum(edit_distance(p, r) for p, r in zip(preds, refs))
    return errs / max(1, sum(len(r) for r in refs))


def wer(preds, refs):
    errs = sum(edit_distance(p.split(), r.split()) for p, r in zip(preds, refs))
    return errs / max(1, sum(len(r.split()) for r in refs))


# ---------- data ----------
def load_rows(data_dir):
    rows = []
    with open(os.path.join(data_dir, "labels.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            text = (r.get("text") or "").strip()
            path = os.path.join(data_dir, "images", r["file_name"])
            if text and os.path.exists(path):
                rows.append({"file_name": r["file_name"], "text": text})
    return rows


def split_rows(rows, val_frac=0.15, seed=42):
    """Split by source page so lines from one page never sit in both sets."""
    pages = sorted({r["file_name"].rsplit("_", 1)[0] for r in rows})
    rng = random.Random(seed)
    if len(pages) >= 4:
        rng.shuffle(pages)
        val_pages = set(pages[: max(1, round(len(pages) * val_frac))])
        val = [r for r in rows if r["file_name"].rsplit("_", 1)[0] in val_pages]
        train = [r for r in rows if r["file_name"].rsplit("_", 1)[0] not in val_pages]
    else:
        print("Few pages: falling back to a random line split.")
        rows = rows[:]
        rng.shuffle(rows)
        n = max(1, round(len(rows) * val_frac))
        val, train = rows[:n], rows[n:]
    return train, val


def augment(img):
    img = img.rotate(random.uniform(-2, 2), expand=True, fillcolor=(255, 255, 255))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 1.15))
    return ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.2))


class Lines(torch.utils.data.Dataset):
    def __init__(self, rows, img_dir, processor, aug):
        self.rows, self.img_dir, self.p, self.aug = rows, img_dir, processor, aug

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(os.path.join(self.img_dir, r["file_name"])).convert("RGB")
        if self.aug:
            img = augment(img)
        pv = self.p(images=img, return_tensors="pt").pixel_values[0]
        tok = self.p.tokenizer
        ids = tok(r["text"], padding="max_length", max_length=MAX_LEN, truncation=True).input_ids
        ids = [t if t != tok.pad_token_id else -100 for t in ids]
        return {"pixel_values": pv, "labels": torch.tensor(ids)}


@torch.no_grad()
def predict(model, processor, rows, img_dir, device, bs=8):
    model.eval()
    out = []
    for i in range(0, len(rows), bs):
        imgs = [Image.open(os.path.join(img_dir, r["file_name"])).convert("RGB")
                for r in rows[i:i + bs]]
        pv = processor(images=imgs, return_tensors="pt").pixel_values.to(device)
        ids = model.generate(pv, max_length=MAX_LEN, num_beams=4,
                             early_stopping=True, no_repeat_ngram_size=3)
        out += [t.strip() for t in processor.batch_decode(ids, skip_special_tokens=True)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset")
    ap.add_argument("--model", default="microsoft/trocr-base-handwritten")
    ap.add_argument("--out", default="trocr-finetuned")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-5)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: no GPU found. Training on CPU will be very slow. Use Colab.")
    use_amp = device == "cuda"

    rows = load_rows(args.data)
    train_rows, val_rows = split_rows(rows)
    img_dir = os.path.join(args.data, "images")
    print(f"{len(rows)} labeled lines -> {len(train_rows)} train / {len(val_rows)} validation")
    if len(train_rows) < 50:
        print("Note: under ~100 lines, gains will be small. More labels = better results.")

    processor = TrOCRProcessor.from_pretrained(args.model)
    model = VisionEncoderDecoderModel.from_pretrained(args.model).to(device)

    val_refs = [r["text"] for r in val_rows]
    base_preds = predict(model, processor, val_rows, img_dir, device)
    base_cer, base_wer = cer(base_preds, val_refs), wer(base_preds, val_refs)
    print(f"\nBEFORE training  CER {base_cer:.1%}  WER {base_wer:.1%}\n")

    loader = torch.utils.data.DataLoader(
        Lines(train_rows, img_dir, processor, aug=True),
        batch_size=args.bs, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    best_cer, best_wer, best_preds = base_cer, base_wer, base_preds
    saved = False
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for batch in loader:
            pv = batch["pixel_values"].to(device)
            labels = batch["labels"].to(device)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                loss = model(pixel_values=pv, labels=labels).loss
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            total += loss.item()

        preds = predict(model, processor, val_rows, img_dir, device)
        c, w = cer(preds, val_refs), wer(preds, val_refs)
        flag = ""
        if c < best_cer:
            best_cer, best_wer, best_preds, saved = c, w, preds, True
            model.save_pretrained(args.out)
            processor.save_pretrained(args.out)
            flag = "  <- saved"
        print(f"epoch {epoch:2d}  loss {total / len(loader):.3f}  val CER {c:.1%}  WER {w:.1%}{flag}")

    print(f"\nBEFORE  CER {base_cer:.1%}  WER {base_wer:.1%}")
    print(f"AFTER   CER {best_cer:.1%}  WER {best_wer:.1%}")
    if saved:
        print(f"\nBest model saved to ./{args.out}\n\nExamples (reference | before | after):")
        for r, b, a in list(zip(val_refs, base_preds, best_preds))[:8]:
            print(f"  REF   {r}\n  BEFORE {b}\n  AFTER  {a}\n")
    else:
        print("\nFine-tuning did not beat the original model. Add more labeled lines "
              "(and more pages/writers) and try again.")


if __name__ == "__main__":
    main()