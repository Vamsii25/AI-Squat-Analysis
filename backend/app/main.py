import os
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config
from . import database


app = FastAPI(
    title="Squat Check API",
    version="1.1.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DIRECTORIES
# ============================================================

os.makedirs(config.UPLOAD_DIR, exist_ok=True)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)


# ============================================================
# STATIC MEDIA
# ============================================================

app.mount(
    "/media",
    StaticFiles(directory=config.OUTPUT_DIR),
    name="media"
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    """
    Connect to MongoDB when FastAPI starts.
    """
    await database.connect_mongodb()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
async def health():
    """
    Check whether FastAPI and MongoDB are working.
    """

    try:
        await database.ping_mongodb()

        return {
            "ok": True,
            "service": "squat-check-api",
            "mongodb": "connected"
        }

    except Exception as exc:

        return {
            "ok": False,
            "service": "squat-check-api",
            "mongodb": "disconnected",
            "error": str(exc)
        }


# ============================================================
# VIDEO UPLOAD
# ============================================================

@app.post("/api/upload")
async def upload_video(
    video: UploadFile = File(...)
):
    """
    Upload a squat video.

    Flow:

    React
        ↓
    FastAPI (this endpoint)
        ↓
    Save temporary local video
        ↓
    MongoDB GridFS
        ↓
    jobs collection (status="processing", stage="uploaded")
        ↓
    model.py, running separately (`python model.py --watch`), picks the
    job up, downloads the video from GridFS, runs the full analysis, and
    writes stage/status/results back onto this same job document. This
    endpoint does NOT run any of that itself.
    """

    # --------------------------------------------------------
    # Determine extension
    #
    # No format is rejected here -- any video file is accepted, in
    # whatever container/codec it was recorded in. model.py's own
    # pipeline (cv2.VideoCapture) reads it directly; the extension is
    # kept only for readability on disk.
    # --------------------------------------------------------

    ext = os.path.splitext(
        video.filename or ""
    )[1].lower() or ".upload"

    # --------------------------------------------------------
    # Generate unique job ID
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex

    video_path = os.path.join(
        config.UPLOAD_DIR,
        f"{job_id}{ext}"
    )

    size = 0
    gridfs_id = None

    try:

        # ====================================================
        # STEP 1: Save video locally
        # ====================================================

        with open(video_path, "wb") as out_file:

            while chunk := await video.read(1024 * 1024):

                size += len(chunk)

                if size > config.MAX_UPLOAD_BYTES:

                    raise HTTPException(
                        status_code=413,
                        detail="Video is too large."
                    )

                out_file.write(chunk)

        # ----------------------------------------------------
        # Empty file validation
        # ----------------------------------------------------

        if size == 0:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file was empty."
            )

        created_at = datetime.now(timezone.utc)

        # ====================================================
        # STEP 2: Store video in MongoDB GridFS
        # ====================================================

        gridfs_id = await database.store_video_in_gridfs(
            video_path,
            video.filename or f"{job_id}{ext}",
            video.content_type,
            {
                "job_id": job_id,
                "original_filename": video.filename,
            },
        )

        # ====================================================
        # STEP 3: Store job information in MongoDB
        # ====================================================

        await database.jobs_collection.insert_one(
            {
                "job_id": job_id,

                "original_filename": video.filename,

                "content_type": video.content_type,

                "size_bytes": size,

                "video_path": video_path,

                "video_storage": "mongodb_gridfs",

                "gridfs_file_id": gridfs_id,

                "status": "processing",

                "stage": "uploaded",

                "stage_label": "Uploaded and stored in MongoDB",

                "results": None,

                "error": None,

                "created_at": created_at,

                "model_video_window_seconds": (
                    config.VIDEO_LOOKBACK_SECONDS
                ),
            }
        )

        # ====================================================
        # STEP 4: Return response to React
        #
        # No processing is started here -- the job now sits with
        # status="processing", stage="uploaded" until the separately
        # running `python model.py --watch` worker picks it up.
        # ====================================================

        return {
            "job_id": job_id,

            "stored_in_mongodb": True,

            "gridfs_file_id": str(gridfs_id),

            "video_storage": "mongodb_gridfs"
        }

    # ========================================================
    # HTTP EXCEPTION
    # ========================================================

    except HTTPException:

        # Delete GridFS file if it was already created

        if gridfs_id:

            try:

                if database.video_bucket is not None:

                    await database.video_bucket.delete(
                        gridfs_id
                    )

            except Exception:
                pass

        # Delete local file

        if os.path.exists(video_path):

            os.remove(video_path)

        raise

    # ========================================================
    # GENERAL EXCEPTION
    # ========================================================

    except Exception as exc:

        # Delete GridFS file if it was created

        if gridfs_id:

            try:

                if database.video_bucket is not None:

                    await database.video_bucket.delete(
                        gridfs_id
                    )

            except Exception:
                pass

        # Delete local file

        if os.path.exists(video_path):

            os.remove(video_path)

        raise HTTPException(
            status_code=500,
            detail=f"Could not store uploaded video: {exc}"
        )

    # ========================================================
    # CLOSE UPLOAD
    # ========================================================

    finally:

        await video.close()


# ============================================================
# STREAM A VIDEO FROM GRIDFS BY ID
# ============================================================

@app.get("/api/videos/{file_id}")
async def stream_video(file_id: str):
    """
    Stream a video stored in the 'videos' GridFS bucket back to the
    browser. model.py points results.video_url at this route for the
    annotated video it uploads after processing -- this is also usable
    for the original uploaded video via its gridfs_file_id.
    """

    await database.ensure_connection()

    try:
        object_id = ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid video id")

    try:
        grid_out = await database.video_bucket.open_download_stream(object_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Video not found")

    content_type = "video/mp4"
    if grid_out.metadata and grid_out.metadata.get("content_type"):
        content_type = grid_out.metadata["content_type"]

    async def chunk_iterator():
        chunk_size = 1024 * 1024
        while True:
            chunk = await grid_out.read(chunk_size)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        chunk_iterator(),
        media_type=content_type,
        headers={"Content-Length": str(grid_out.length)},
    )


# ============================================================
# JOB STATUS
# ============================================================

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """
    Return processing status and results for a video job.
    """

    job = await database.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "stage_label": job.get("stage_label"),

        "results": job.get(
            "results",
            {}
        ),

        "error": job.get(
            "error"
        ),
    }


# ============================================================
# LATEST VIDEO
# ============================================================

@app.get("/api/latest-video")
async def latest_video():
    """
    Return the newest uploaded video within
    the configured last-minute window.
    """

    job = await database.get_latest_video_within(
        config.VIDEO_LOOKBACK_SECONDS
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="No video was uploaded in the last minute."
        )


    # ============================================================
# RESULTS HISTORY
# ============================================================

@app.get("/api/results")
async def list_results(limit: int = 50):
    """
    Return saved analyses from MongoDB, newest first.
    Used by the React Results page.
    """

    await database.ensure_connection()

    cursor = database.jobs_collection.find(
        {"status": "done"},
        {
            "_id": 0,               # ObjectId isn't JSON-serialisable
            "gridfs_file_id": 0,    # ObjectId
            "video_path": 0,        # don't expose local file paths
        },
    ).sort("created_at", -1).limit(max(1, min(limit, 200)))

    return await cursor.to_list(length=limit)

    

    # Remove MongoDB internal ID

    job.pop("_id", None)

    # Do not expose local filesystem path

    job.pop("video_path", None)

    # Convert ObjectId to string

    if job.get("gridfs_file_id"):

        job["gridfs_file_id"] = str(
            job["gridfs_file_id"]
        )

    return job