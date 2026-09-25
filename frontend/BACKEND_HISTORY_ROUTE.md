# Backend route the Results page needs

The frontend calls `GET /api/results?limit=50` and expects a JSON list of the
job documents saved in MongoDB (newest first). Add this to your FastAPI app,
adjusting `jobs_collection` to whatever collection your `/api/status/{job_id}`
route already reads from:

```python
@app.get("/api/results")
async def list_results(limit: int = 50):
    cursor = jobs_collection.find(
        {"status": "done"},
        {"_id": 0},            # drop ObjectId so it is JSON-serialisable
    ).sort("created_at", -1).limit(limit)

    # Motor (async driver):
    return [doc async for doc in cursor]
    # PyMongo (sync driver) -> return list(cursor)
```

Each document should contain `job_id`, `status`, `created_at` and `results`
(the same `results` object `/api/status/{job_id}` returns). If your documents
use `_id` as the job id, replace `{"_id": 0}` with a projection that keeps it
and convert it with `str(doc["_id"])`.
