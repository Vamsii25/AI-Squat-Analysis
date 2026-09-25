import os
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorGridFSBucket,
)

from . import config


# ============================================================
# GLOBAL MONGODB OBJECTS
# ============================================================

client = None
db = None
jobs_collection = None
video_bucket = None


# ============================================================
# CONNECT TO MONGODB
# ============================================================

async def connect_mongodb():
    """
    Create the MongoDB client and initialize:

        - database
        - jobs collection
        - GridFS video bucket
    """

    global client
    global db
    global jobs_collection
    global video_bucket

    # Avoid creating multiple clients
    if client is not None:
        try:
            await client.admin.command("ping")
            return True
        except Exception:
            client = None
            db = None
            jobs_collection = None
            video_bucket = None

    # Create MongoDB client inside FastAPI event loop
    client = AsyncIOMotorClient(
        config.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )

    # Verify MongoDB connection
    await client.admin.command("ping")

    # Select database
    db = client[config.MONGO_DB_NAME]

    # Jobs collection
    jobs_collection = db["jobs"]

    # GridFS bucket
    #
    # MongoDB creates:
    #
    # videos.files
    # videos.chunks
    #
    video_bucket = AsyncIOMotorGridFSBucket(
        db,
        bucket_name="videos",
    )

    return True


# ============================================================
# ENSURE MONGODB CONNECTION
# ============================================================

async def ensure_connection():
    """
    Make sure MongoDB is initialized before using
    jobs_collection or video_bucket.
    """

    global client

    if client is None:
        await connect_mongodb()
        return

    try:
        await client.admin.command("ping")
    except Exception:
        await connect_mongodb()


# ============================================================
# PING MONGODB
# ============================================================

async def ping_mongodb():
    """
    Check whether MongoDB is available.
    """

    await ensure_connection()

    await client.admin.command("ping")

    return True


# ============================================================
# CLOSE MONGODB
# ============================================================

async def close_mongodb():
    """
    Close MongoDB connection.
    """

    global client
    global db
    global jobs_collection
    global video_bucket

    if client is not None:
        client.close()

    client = None
    db = None
    jobs_collection = None
    video_bucket = None


# ============================================================
# CREATE JOB
# ============================================================

async def create_job(
    job_id,
    original_filename=None,
    video_path=None,
    gridfs_file_id=None,
    content_type=None,
    file_size=None,
    **extra_fields,
):
    """
    Create a processing job in MongoDB.
    """

    await ensure_connection()

    now = datetime.now(timezone.utc)

    job = {
        "job_id": job_id,
        "original_filename": original_filename,
        "video_path": video_path,
        "gridfs_file_id": (
            str(gridfs_file_id)
            if gridfs_file_id is not None
            else None
        ),
        "content_type": content_type,
        "file_size": file_size,
        "status": "queued",
        "stage": "queued",
        "stage_label": "Queued",
        "created_at": now,
        "updated_at": now,
    }

    # Add any additional fields supplied by main.py
    job.update(extra_fields)

    await jobs_collection.insert_one(job)

    return job


# ============================================================
# GET JOB
# ============================================================

async def get_job(job_id: str):
    """
    Get one job using its job_id.

    This function is required by orchestrator.py.
    """

    await ensure_connection()

    job = await jobs_collection.find_one(
        {
            "job_id": job_id
        }
    )

    return job


# ============================================================
# UPDATE JOB
# ============================================================

async def update_job(
    job_id: str,
    **fields,
):
    """
    Update fields belonging to a job.
    """

    await ensure_connection()

    fields["updated_at"] = datetime.now(
        timezone.utc
    )

    result = await jobs_collection.update_one(
        {
            "job_id": job_id
        },
        {
            "$set": fields
        },
    )

    return result.modified_count > 0


# ============================================================
# DELETE JOB
# ============================================================

async def delete_job(job_id: str):
    """
    Delete a job from MongoDB.
    """

    await ensure_connection()

    result = await jobs_collection.delete_one(
        {
            "job_id": job_id
        }
    )

    return result.deleted_count > 0


# ============================================================
# STORE VIDEO IN MONGODB GRIDFS
# ============================================================

async def store_video_in_gridfs(
    video_path,
    filename,
    content_type="video/mp4",
    metadata=None,
):
    """
    Store uploaded video inside MongoDB GridFS.

    Returns
    -------
    ObjectId
        MongoDB GridFS file ID.
    """

    await ensure_connection()

    if metadata is None:
        metadata = {}

    metadata = dict(metadata)

    # Store MIME type
    metadata["content_type"] = content_type

    # Store timestamp
    metadata["stored_at"] = datetime.now(
        timezone.utc
    )

    # Make sure file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"Video file not found: {video_path}"
        )

    # Upload video
    with open(
        video_path,
        "rb",
    ) as video_file:

        gridfs_id = await video_bucket.upload_from_stream(
            filename,
            video_file,
            metadata=metadata,
        )

    return gridfs_id


# ============================================================
# DOWNLOAD VIDEO FROM GRIDFS
# ============================================================

async def download_video_from_gridfs(
    file_id,
    destination_path,
):
    """
    Download a video stored in MongoDB GridFS
    to a local file.
    """

    await ensure_connection()

    # Convert string ID to ObjectId
    if isinstance(file_id, str):
        try:
            file_id = ObjectId(file_id)
        except Exception as exc:
            raise ValueError(
                f"Invalid GridFS file ID: {file_id}"
            ) from exc

    # Create destination directory
    destination_dir = os.path.dirname(
        destination_path
    )

    if destination_dir:
        os.makedirs(
            destination_dir,
            exist_ok=True,
        )

    # Download GridFS file
    with open(
        destination_path,
        "wb",
    ) as output_file:

        await video_bucket.download_to_stream(
            file_id,
            output_file,
        )

    return destination_path


# ============================================================
# DELETE VIDEO FROM GRIDFS
# ============================================================

async def delete_video_from_gridfs(
    file_id,
):
    """
    Delete a video from MongoDB GridFS.
    """

    await ensure_connection()

    if isinstance(file_id, str):
        try:
            file_id = ObjectId(file_id)
        except Exception as exc:
            raise ValueError(
                f"Invalid GridFS file ID: {file_id}"
            ) from exc

    await video_bucket.delete(
        file_id
    )

    return True


# ============================================================
# GET LATEST VIDEO WITHIN TIME WINDOW
# ============================================================

async def get_latest_video_within(
    seconds=60,
):
    """
    Find the most recently uploaded job
    within the specified number of seconds.
    """

    await ensure_connection()

    cutoff_time = (
        datetime.now(timezone.utc)
        - timedelta(seconds=seconds)
    )

    job = await jobs_collection.find_one(
        {
            "created_at": {
                "$gte": cutoff_time
            }
        },
        sort=[
            (
                "created_at",
                -1,
            )
        ],
    )

    return job


# ============================================================
# GET LATEST JOB
# ============================================================

async def get_latest_job():
    """
    Get the most recently created job.
    """

    await ensure_connection()

    job = await jobs_collection.find_one(
        {},
        sort=[
            (
                "created_at",
                -1,
            )
        ],
    )

    return job


# ============================================================
# GET ALL JOBS
# ============================================================

async def get_jobs(
    limit=50,
):
    """
    Get recent jobs.
    """

    await ensure_connection()

    cursor = (
        jobs_collection
        .find({})
        .sort(
            "created_at",
            -1,
        )
        .limit(limit)
    )

    jobs = await cursor.to_list(
        length=limit
    )

    return jobs