# Squat Check — Technical Documentation

An AI-powered squat-form analysis application. A user uploads a side-view
squat video; a background worker runs pose estimation, tracks the barbell,
detects reps, and sends the measurements to an LLM that grades each rep
against a document-derived rulebook (`SQUAT_SKILL`), returning per-criterion
findings plus an annotated video.

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite dev server, default `http://localhost:5173`) |
| Backend API | FastAPI (Python), served by Uvicorn |
| Background worker | Plain Python script (`model.py`), run as a **separate process** |
| Database | MongoDB — one `jobs` collection + a `videos` GridFS bucket |
| Pose estimation | MediaPipe Pose Landmarker (`pose_landmarker_full.task`) |
| Bar tracking | OpenCV Hough Circle Transform (heuristic, no ML model) |
| Rep detection | SciPy `find_peaks` on the hip's vertical trajectory |
| LLM assessment | Groq API (auto-selects an available chat model, e.g. Llama 3.3 / GPT-OSS) |
| Video re-encode | ffmpeg (optional, for browser-playable H.264 output) |

The backend is deliberately split into **two independent processes** that
only ever talk to each other through MongoDB — never directly:

- `app/` — the FastAPI server. Handles uploads, status polling, and
  streaming video back to the browser. It never touches MediaPipe, OpenCV,
  or Groq.
- `model.py` — the worker. Has zero HTTP endpoints. It polls MongoDB for
  unprocessed jobs, does all the heavy computer-vision and LLM work, and
  writes the results back onto the same job document.

This means the API stays fast and responsive while a squat video (which can
take anywhere from several seconds to a couple of minutes to process) is
being analyzed in the background.

---

## 2. Architecture Diagram

```mermaid
flowchart TB
    subgraph Client
        FE["React frontend<br/>(localhost:5173)"]
    end

    subgraph Backend["Backend (Python)"]
        API["FastAPI server<br/>app/main.py<br/>(Terminal 1: uvicorn)"]
        WORKER["model.py worker<br/>(Terminal 2: python run_worker.py)"]
    end

    subgraph DataStores["MongoDB (squat_check database)"]
        JOBS[("jobs collection<br/>status / stage / results")]
        GRIDFS[("videos GridFS bucket<br/>videos.files + videos.chunks")]
    end

    GROQ[["Groq API<br/>(LLM assessment)"]]
    MP[["MediaPipe<br/>pose_landmarker_full.task<br/>(local, downloaded once)"]]

    FE -- "1. POST /api/upload" --> API
    API -- "2. save video bytes" --> GRIDFS
    API -- "3. insert job doc<br/>(stage=uploaded)" --> JOBS
    API -- "4. { job_id }" --> FE

    FE -- "5. GET /api/status/{job_id}<br/>(polls every few seconds)" --> API
    API -- "reads" --> JOBS

    WORKER -- "6. polls every 5s for<br/>stage=uploaded" --> JOBS
    WORKER -- "7. downloads original video" --> GRIDFS
    WORKER -- "8. runs pose + bar tracking" --> MP
    WORKER -- "9. sends SKILL + measurements" --> GROQ
    GROQ -- "10. structured findings JSON" --> WORKER
    WORKER -- "11. uploads annotated video" --> GRIDFS
    WORKER -- "12. writes results, status=done" --> JOBS

    FE -- "13. GET /api/videos/{annotated_id}<br/>(stream annotated video)" --> API
    API -- "reads" --> GRIDFS
