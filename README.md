# Handwritten Notes Digitizer

Converts photos of handwritten notes into editable, searchable digital text.
Built for a Software Freedom Day open-source demo stall — every component
below is free/open-source software.

## Architecture

```
React (frontend)  -->  Express/Node API (backend)  -->  MongoDB (storage/search)
                              |
                              v
                   Flask + TrOCR (ml-service, Python)
```

The web app is a standard MERN stack (MongoDB, Express, React, Node).
Handwriting recognition itself needs a real ML model (TrOCR), which is
PyTorch-based — there is no JavaScript model that reaches comparable
accuracy. So the Node backend calls a small local Python microservice
(`ml-service/`) for just the recognition step, over plain HTTP on your
own machine. Everything else (app logic, storage, search, export, UI)
is pure MERN.

## Open source components used

| Purpose | Tool | License |
|---|---|---|
| Backend framework | Express (Node.js) | MIT |
| Database | MongoDB | SSPL (source-available) |
| Frontend | React | MIT |
| Image preprocessing | OpenCV (opencv-python) | Apache 2.0 |
| Handwriting recognition | TrOCR (microsoft/trocr-base-handwritten, via Hugging Face Transformers) | MIT |
| Spell cleanup | pyspellchecker | MIT |
| DOCX export | `docx` npm package | MIT |
| XML/TXT export | Node built-ins | - |
| Search | MongoDB text index | - |

## A note on accuracy

TrOCR's published benchmarks on the IAM handwriting dataset land in the
90-96% character-accuracy range **on clean, well-lit handwriting**. Real
stall conditions (phone camera, messy handwriting, shadows) will pull
that down. To get the best results:
- Good, even lighting when photographing notes (no shadows across the page)
- Straight-on angle, not tilted
- Dark ink on plain paper works best
- The preprocessing step (denoise/deskew/binarize) matters a lot — don't skip it

Do not present this as a guaranteed fixed percentage at your stall — present
it as "state-of-the-art open source handwriting recognition, backed by
published TrOCR benchmarks," and let the live demo speak for itself.

## Reducing RAM usage

If the app is eating far more RAM than expected, it's almost always PyTorch,
not Node/React/Mongo. Do these in order - each one meaningfully helps, and
together they should bring total usage down from several GB to roughly
1.5-2.5GB for `ml-service`, plus a few hundred MB each for backend/frontend/Mongo.

1. **Install the CPU-only build of PyTorch.** A plain `pip install torch`
   on many systems pulls in the full CUDA-enabled build, which is larger
   and uses more RAM at runtime even though your laptop likely has no
   NVIDIA GPU to use it with. Instead, inside `ml-service/venv`, run:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install -r requirements.txt
   ```
   (installing torch first, then the rest, avoids pip pulling the GPU build as a dependency)

2. **Use the small TrOCR model.** `recognize.py` now defaults to
   `microsoft/trocr-small-handwritten` (~250MB) instead of the base model
   (~1.3GB). Small is noticeably lighter and still solid for a demo. If
   you want to try base for slightly better accuracy once RAM isn't tight,
   set an environment variable before starting the service:
   ```bash
   export TROCR_MODEL=microsoft/trocr-base-handwritten   # Windows: set TROCR_MODEL=...
   python app.py
   ```

3. **Run the React frontend as a production build instead of the dev server.**
   `npm start` runs webpack's dev server, which is much heavier than the
   built app. For your stall, build once and serve statically:
   ```bash
   cd frontend
   npm run build
   npx serve -s build -l 3000
   ```

4. **Close unrelated apps during the demo** - especially other browser
   tabs/windows, since Chrome itself is a heavy RAM user, and other IDEs.

5. **Restart `ml-service` between long idle periods** if you notice memory
   creeping up over many uploads - this is normal for long-running Python/ML
   processes and a fresh restart clears it instantly.

These changes are already applied in the code you have (small model by
default, num_beams reduced, memory cleanup after each request) - step 1 and
3 are things you do yourself when installing/running.

## Prerequisites

- Node.js 18+
- Python 3.9+
- MongoDB running locally (or a free MongoDB Atlas cluster)
- ~2GB free disk space (for the TrOCR model weights, downloaded on first run)

## Setup

### 1. ML service (Python)

```bash
cd ml-service
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python app.py
```

(torch is installed separately, CPU-only - see "Reducing RAM usage" below for why)

Runs on `http://localhost:5001`. First run downloads the TrOCR model
(~1.3GB) from Hugging Face — needs internet, only once.

### 2. Backend (Node/Express)

```bash
cd backend
npm install
cp .env.example .env      # edit MONGO_URI if needed
npm start
```

Runs on `http://localhost:5000`.

### 3. Frontend (React)

```bash
cd frontend
npm install
npm start
```

Runs on `http://localhost:3000`.

## Before your demo

- Start MongoDB, then ml-service, then backend, then frontend, in that order.
- Do a full dry run at home with 3-4 sample handwritten notes.
- Keep the ml-service terminal visible — if it crashes, recognition silently fails.
- Load the TrOCR model once before the stall opens (first request is slow,
  later ones are fast) by uploading one test image.

## Project structure

```
handwriting-digitizer/
├── backend/          Express API + MongoDB models + export logic
├── ml-service/        Flask + OpenCV + TrOCR recognition service
├── frontend/          React app (upload, edit, export, search)
└── README.md
```
