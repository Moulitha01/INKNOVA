"""
Build a fine-tuning dataset from photos of handwritten notes.

Usage (run inside ml-service, venv active):
    python make_dataset.py photos            # crops + TrOCR draft text
    python make_dataset.py photos --no-draft # crops only (fast, blank text)

Output in ./dataset:
    images/            one PNG per detected line
    label.html         open in a browser, correct the text, download labels.csv
    labels.csv         (you create it by clicking Download in label.html)
"""

import os
import sys
import json
import argparse
from PIL import Image
from preprocess import preprocess_image, segment_lines

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

PAGE = """<!doctype html><meta charset="utf-8"><title>Label lines</title>
<style>
body{font-family:-apple-system,Segoe UI,sans-serif;max-width:900px;margin:0 auto;padding:0 12px 40px}
.bar{position:sticky;top:0;background:#fff;padding:10px 0;border-bottom:1px solid #ddd;z-index:2}
.row{border:1px solid #ddd;border-radius:8px;padding:10px;margin:10px 0}
.row img{max-width:100%;max-height:90px;display:block;background:#f5f5f5}
.row input{width:100%;font-size:16px;padding:6px;margin-top:6px;box-sizing:border-box}
button{padding:8px 14px;font-size:14px;cursor:pointer}
small{color:#666}
</style>
<div class="bar"><b id="n"></b>
<button onclick="save()">Download labels.csv</button><br>
<small>Make each box match the image exactly. Clear a box to skip a bad crop.
Save the downloaded file as dataset/labels.csv.</small></div>
<div id="rows"></div>
<script>
const DATA = __DATA__;
const box = document.getElementById("rows");
const KEY = "labels:" + DATA[0].file;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
DATA.forEach((d, i) => {
  const r = document.createElement("div"); r.className = "row";
  r.innerHTML = '<img src="images/' + d.file + '"><input id="t' + i + '">';
  box.appendChild(r);
  const inp = document.getElementById("t" + i);
  inp.value = saved[d.file] !== undefined ? saved[d.file] : d.text;
  inp.addEventListener("input", update);
});
function filled() {
  return DATA.filter((d, i) => document.getElementById("t" + i).value.trim()).length;
}
function update() {
  const s = {};
  DATA.forEach((d, i) => { s[d.file] = document.getElementById("t" + i).value; });
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
  document.getElementById("n").textContent = filled() + " of " + DATA.length + " lines labeled  ";
}
update();
function save() {
  if (!filled()) { alert("No text typed yet. Type the text into the boxes first."); return; }
  let csv = "file_name,text\\n";
  DATA.forEach((d, i) => {
    const t = document.getElementById("t" + i).value.replace(/\\s+/g, " ").trim();
    if (t) csv += d.file + ',"' + t.replace(/"/g, '""') + '"\\n';
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\\ufeff" + csv], {type: "text/csv"}));
  a.download = "labels.csv"; a.click();
}
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", default="photos")
    ap.add_argument("--no-draft", action="store_true", help="skip TrOCR draft text")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.folder) if f.lower().endswith(EXTS))
    if not files:
        sys.exit(f"No images found in '{args.folder}'.")

    out_dir = os.path.join("dataset", "images")
    os.makedirs(out_dir, exist_ok=True)

    recog = None
    if not args.no_draft:
        from recognize import _recognize_line as recog  # loads the model lazily

    rows = []
    for name in files:
        stem = os.path.splitext(name)[0].replace(" ", "_")
        img = Image.open(os.path.join(args.folder, name))
        crops = segment_lines(preprocess_image(img))
        print(f"{name}: {len(crops)} lines")
        for i, crop in enumerate(crops, 1):
            fname = f"{stem}_{i:02d}.png"
            crop.save(os.path.join(out_dir, fname))
            text = recog(crop) if recog else ""
            rows.append({"file": fname, "text": text})

    html = PAGE.replace("__DATA__", json.dumps(rows).replace("</", "<\\/"))
    with open(os.path.join("dataset", "label.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nDone: {len(rows)} line crops. Open dataset/label.html in your browser.")


if __name__ == "__main__":
    main()