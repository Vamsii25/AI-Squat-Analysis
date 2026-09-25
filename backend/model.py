"""
model.py -- Squat-check local worker.

Runs Model 1 (MediaPipe pose + heuristic bar tracking + rep detection) and
Model 2 (Groq LLM assessment agent, grounded in SQUAT_SKILL) exactly as in the
original notebook, but wired for local/backend use instead of Colab:

  INPUT:  a job document in MongoDB (db: squat_check, collection: jobs).
          The uploaded video itself lives in GridFS -- job["gridfs_file_id"]
          points at it (this matches the job documents your upload service
          already writes, e.g. status="processing", stage="uploaded").

  OUTPUT: the same job document, updated in place:
          - job["status"]        -> "done" | "error"   (what the React frontend polls for)
          - job["stage"]         -> progresses through "processing_pose" /
                                     "assessing" / "annotating" / "saving" / "done"
          - job["stage_label"]   -> human-readable status for the UI
          - job["results"]       -> { overall_summary, findings, video_data,
                                       low_quality_warning, annotated_gridfs_file_id, video_url }
          - job["error"]         -> set only on failure
          The annotated (skeleton + bar-trail + HUD) video is written back into
          GridFS too, so the frontend can stream it without touching local disk.

Nothing about the actual squat-analysis logic (geometry, pose landmarker, bar
tracker, rep detector, annotator, SQUAT_SKILL, the LLM assessment agent) was
changed from the notebook -- only the I/O boundary (video in, results out).

Usage
-----
  # one-shot: process a single job by its job_id
  python model.py --job-id bc15727088c74daca612dd5c1c83a175

  # worker mode: keep polling MongoDB for the next uploaded job forever
  python model.py --watch

Configuration
-------------
  GROQ_API_KEY_IN_CODE  (below) paste your Groq key there. If left as the
                        placeholder, the GROQ_API_KEY environment variable is used.

Environment variables (all optional)
------------------------------------
  MONGO_URI        MongoDB connection string   (default: mongodb://localhost:27017)
  MONGO_DB         Database name               (default: squat_check)
  MONGO_COLLECTION Jobs collection name         (default: jobs)
  GRIDFS_BUCKET    GridFS bucket/prefix name    (default: videos -- i.e. videos.files/videos.chunks)
  GROQ_API_KEY     Groq key (only used if GROQ_API_KEY_IN_CODE is not filled in)
  GROQ_MODEL       Force a specific Groq model  (optional -- auto-picked otherwise)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
import pandas as pd
from bson import ObjectId
from gridfs import GridFS
from pymongo import MongoClient
from scipy.signal import find_peaks

# ---------------------------------------------------------------------------
# Config (env-driven, sensible local defaults)
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB", "squat_check")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION", "jobs")
GRIDFS_BUCKET = os.environ.get("GRIDFS_BUCKET", "videos")  # matches videos.files / videos.chunks

# ---------------------------------------------------------------------------
# GROQ API KEY  --  paste your key between the quotes below.
# Get one at https://console.groq.com/keys  (it starts with "gsk_").
# Do NOT upload this file to GitHub or share it while the key is inside.
# ---------------------------------------------------------------------------
GROQ_API_KEY_IN_CODE = "Your_groq_api_key_here"

GROQ_API_KEY = (
    GROQ_API_KEY_IN_CODE
    if GROQ_API_KEY_IN_CODE.startswith("gsk_") and "PASTE" not in GROQ_API_KEY_IN_CODE
    else (os.environ.get("GROQ_API_KEY") or "")
).strip().strip('"').strip("'")

GROQ_MODEL_OVERRIDE = os.environ.get("GROQ_MODEL")

MAX_DURATION_S_DEFAULT = 60
TARGET_MAX_FRAMES = 1800
POLL_INTERVAL_S = 5

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(_MODEL_DIR, "pose_landmarker_full.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/1/pose_landmarker_full.task"
)

CONFIDENCE_FLOOR = 0.5  # below this, treat the underlying measurement as unusable


# ---------------------------------------------------------------------------
# 1) SQUAT_SKILL -- the reusable squat skill (unchanged from the notebook).
#    This is the ONLY place squat-technique knowledge lives; the LLM
#    assessment agent is told to use ONLY these rules.
# ---------------------------------------------------------------------------

SQUAT_SKILL = {
    "skill_name": "low_bar_back_squat_standards",
    "skill_version": "1.0",
    "source_document": "Document_for_skill.pdf (reference pages 1-35 = combined PDF pages 4-38)",
    "criteria": [
        {
            "id": "depth",
            "criterion": "Squat depth",
            "rule": (
                "At the bottom, the plane through the hip joint (crease of the shorts) "
                "must drop below the plane of the top of the patella (knee) -- i.e. the hip "
                "joint goes below parallel with the ground. Anything shallower is a partial squat."
            ),
            "source_pages": [5, 22, 23],
            "assessable_from_side_view": True,
            "notes": "This is the canonical side-view measurement (Fig 2-1): compare hip-joint height to top-of-patella height at the rep's bottom frame.",
        },
        {
            "id": "back_angle",
            "criterion": "Back angle",
            "rule": (
                "The back angle (plane of torso vs. floor) should be inclined -- roughly 45 degrees "
                "at the bottom for a low-bar squat -- not vertical. Back angle largely determines the "
                "hip angle and whether the hamstrings/hips (not just the knees) can drive the lift."
            ),
            "source_pages": [12, 24, 25, 38],
            "assessable_from_side_view": True,
            "notes": "Directly measurable in profile: angle between the torso line (hip-to-shoulder) and the floor.",
        },
        {
            "id": "bar_path_balance",
            "criterion": "Bar path / midfoot balance",
            "rule": (
                "The lifter/barbell system must stay balanced with the bar (and its vertical path) "
                "directly over the midfoot throughout the rep. Bar forward or behind the midfoot is a "
                "leverage/balance fault, more critical as load increases."
            ),
            "source_pages": [11, 12, 13, 14, 15],
            "assessable_from_side_view": True,
            "notes": "Bar's horizontal (x) offset from the tracked midfoot point, sampled across the rep, is a direct side-view measurement.",
        },
        {
            "id": "hip_drive_direction",
            "criterion": "Hip drive out of the bottom",
            "rule": (
                "Out of the bottom, the hips should drive straight UP, not forward first. "
                "The chest rising ahead of the hips (hips shooting back/up while chest dives) "
                "indicates lost hip drive and an over-vertical recovery."
            ),
            "source_pages": [24, 25, 26, 36, 38],
            "assessable_from_side_view": True,
            "notes": "Approximated from the trajectory of the tracked hip point vs. shoulder point in the first ~20% of the ascent; treat as a directional signal, not a precise force measurement.",
        },
        {
            "id": "knee_position",
            "criterion": "Knee tracking (knees out, over the feet)",
            "rule": (
                "Knees should track out in line with the feet (thighs parallel to feet), not "
                "collapse inward, and should sit only slightly forward of the toes at the bottom."
            ),
            "source_pages": [16, 17, 20, 24, 38],
            "assessable_from_side_view": "partial",
            "notes": "Side view CAN estimate forward knee travel relative to the toe/ankle. It CANNOT reliably assess inward knee collapse (valgus) or lateral tracking -- that needs a front-on view. Report knee-forward-of-toe only; mark lateral tracking as cannot_assess from a single side-view video.",
        },
        {
            "id": "eye_gaze_head_position",
            "criterion": "Head / neck position (eye gaze)",
            "rule": (
                "Chin should stay down/neutral, eyes on a fixed floor point a few feet ahead. "
                "Looking up (cervical hyperextension) disrupts hip drive and loads the neck unsafely."
            ),
            "source_pages": [26, 27, 28, 29, 38],
            "assessable_from_side_view": "partial",
            "notes": "Head/neck angle relative to the torso is visible in profile as a proxy for gaze direction, but true eye-gaze direction is not directly observable. Report as a lower-confidence estimate.",
        },
        {
            "id": "bar_placement",
            "criterion": "Bar placement on the back (low-bar position)",
            "rule": (
                'For the low-bar squat this document teaches, the bar should sit just below the '
                'spine of the scapula, on the rear-deltoid "shelf" -- not up on the traps (high-bar).'
            ),
            "source_pages": [15, 16, 32, 33, 34],
            "assessable_from_side_view": "partial",
            "notes": "Vertical bar position on the back is visible in profile but precise shelf/scapula-spine placement needs a close, unobstructed view of the back; treat low-confidence tracking as cannot_assess rather than guessing.",
        },
        {
            "id": "stance_foot_turnout",
            "criterion": "Stance width and toe-out angle",
            "rule": "Heels roughly shoulder width apart, toes turned out about 30 degrees.",
            "source_pages": [17, 23, 24, 35],
            "assessable_from_side_view": False,
            "notes": "A single side-view video shows only one foot in profile and cannot determine bilateral stance width or toe-out angle. Always cannot_assess from side view alone.",
        },
    ],
}


# ---------------------------------------------------------------------------
# 2) Geometry helpers (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class Point:
    x: float
    y: float
    visibility: float = 1.0

    def is_visible(self, threshold: float = 0.5) -> bool:
        return self.visibility >= threshold


def vector(a: Point, b: Point):
    return (b.x - a.x, b.y - a.y)


def angle_between_vectors_deg(v1, v2) -> Optional[float]:
    mag1, mag2 = math.hypot(*v1), math.hypot(*v2)
    if mag1 < 1e-6 or mag2 < 1e-6:
        return None
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cos_theta = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_theta))


def joint_angle_deg(a: Point, b: Point, c: Point, vis_threshold: float = 0.5) -> Optional[float]:
    if not (a.is_visible(vis_threshold) and b.is_visible(vis_threshold) and c.is_visible(vis_threshold)):
        return None
    return angle_between_vectors_deg(vector(b, a), vector(b, c))


def back_angle_deg(shoulder: Point, hip: Point, vis_threshold: float = 0.5) -> Optional[float]:
    if not (shoulder.is_visible(vis_threshold) and hip.is_visible(vis_threshold)):
        return None
    angle = angle_between_vectors_deg(vector(hip, shoulder), (1.0, 0.0))
    if angle is None:
        return None
    return angle if angle <= 90 else 180 - angle


def knee_angle_deg(hip, knee, ankle, vis_threshold=0.5):
    return joint_angle_deg(hip, knee, ankle, vis_threshold)


def depth_meets_standard(hip: Point, knee: Point, vis_threshold: float = 0.5) -> Optional[bool]:
    if not (hip.is_visible(vis_threshold) and knee.is_visible(vis_threshold)):
        return None
    return hip.y >= knee.y


def knee_toe_horizontal_offset_px(knee: Point, toe: Point, vis_threshold: float = 0.5) -> Optional[float]:
    if not (knee.is_visible(vis_threshold) and toe.is_visible(vis_threshold)):
        return None
    return knee.x - toe.x


def normalize_by_shin_length(value_px, knee: Point, ankle: Point) -> Optional[float]:
    shin_len = math.hypot(knee.x - ankle.x, knee.y - ankle.y)
    if shin_len < 1e-6 or value_px is None:
        return None
    return value_px / shin_len


def bar_horizontal_deviation_from_midfoot(
    bar_center_x, ankle: Point, foot_index: Optional[Point] = None, vis_threshold: float = 0.5
) -> Optional[float]:
    if not ankle.is_visible(vis_threshold):
        return None
    midfoot_x = ankle.x
    if foot_index is not None and foot_index.is_visible(vis_threshold):
        midfoot_x = (ankle.x + foot_index.x) / 2.0
    return bar_center_x - midfoot_x


# ---------------------------------------------------------------------------
# 3) Pose landmarker (unchanged) -- downloads the MediaPipe model once, locally
# ---------------------------------------------------------------------------

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

LANDMARK_INDEX = {
    "nose": 0, "left_ear": 7, "right_ear": 8,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}


@dataclass
class FrameLandmarks:
    frame_index: int
    timestamp_ms: float
    points: dict = field(default_factory=dict)
    detected: bool = False

    def get(self, name):
        return self.points.get(name)


def ensure_model_downloaded() -> str:
    os.makedirs(_MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        import urllib.request
        print("Downloading MediaPipe pose model (one-time, ~30MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


class PoseProcessor:
    def __init__(self, model_path=None, min_pose_confidence: float = 0.5):
        model_path = model_path or ensure_model_downloaded()
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=min_pose_confidence,
            min_tracking_confidence=min_pose_confidence,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def process_frame(self, frame_rgb, frame_index: int, timestamp_ms: int) -> FrameLandmarks:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        fl = FrameLandmarks(frame_index=frame_index, timestamp_ms=timestamp_ms)
        if not result.pose_landmarks:
            return fl
        landmarks = result.pose_landmarks[0]
        h, w = frame_rgb.shape[0], frame_rgb.shape[1]
        for name, idx in LANDMARK_INDEX.items():
            lm = landmarks[idx]
            visibility = getattr(lm, "visibility", 1.0) or 0.0
            fl.points[name] = Point(x=lm.x * w, y=lm.y * h, visibility=visibility)
        fl.detected = True
        return fl

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def pick_side(frame: FrameLandmarks) -> str:
    left_keys = ["left_shoulder", "left_hip", "left_knee", "left_ankle"]
    right_keys = ["right_shoulder", "right_hip", "right_knee", "right_ankle"]
    left_vis = [frame.get(k).visibility for k in left_keys if frame.get(k)]
    right_vis = [frame.get(k).visibility for k in right_keys if frame.get(k)]
    left_avg = sum(left_vis) / len(left_vis) if left_vis else 0.0
    right_avg = sum(right_vis) / len(right_vis) if right_vis else 0.0
    return "left" if left_avg >= right_avg else "right"


# ---------------------------------------------------------------------------
# 4) Heuristic bar tracker (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class BarPosition:
    frame_index: int
    x: Optional[float]
    y: Optional[float]
    radius: Optional[float]
    confidence: float
    is_estimate: bool = True


def _search_window(shoulder: Point, hip: Point, frame_w: int, frame_h: int):
    torso_len = math.hypot(hip.x - shoulder.x, hip.y - shoulder.y)
    half_w = max(60.0, torso_len * 1.2)
    half_h = max(60.0, torso_len * 0.9)
    x0 = int(max(0, shoulder.x - half_w)); x1 = int(min(frame_w, shoulder.x + half_w))
    y0 = int(max(0, shoulder.y - half_h)); y1 = int(min(frame_h, shoulder.y + half_h * 0.6))
    return x0, y0, x1, y1


def detect_bar_in_frame(frame_bgr, frame_index, shoulder, hip, prev=None) -> BarPosition:
    h, w = frame_bgr.shape[:2]
    if shoulder is None or hip is None:
        return BarPosition(frame_index, None, None, None, confidence=0.0)
    x0, y0, x1, y1 = _search_window(shoulder, hip, w, h)
    if x1 <= x0 or y1 <= y0:
        return BarPosition(frame_index, None, None, None, confidence=0.0)
    roi = frame_bgr[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)
    min_radius = max(10, int(0.15 * (x1 - x0)))
    max_radius = max(min_radius + 5, int(0.55 * (x1 - x0)))
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max_radius,
        param1=100, param2=30, minRadius=min_radius, maxRadius=max_radius,
    )
    if circles is None:
        return BarPosition(frame_index, None, None, None, confidence=0.0)
    circles = np.round(circles[0, :]).astype(int)

    def score(c):
        cx, cy, r = c
        s = 1.0
        if prev is not None and prev.x is not None:
            dist = math.hypot(cx - (prev.x - x0), cy - (prev.y - y0))
            s -= min(0.6, dist / max_radius)
        return s

    best = max(circles, key=score)
    cx, cy, r = best
    return BarPosition(frame_index, float(cx + x0), float(cy + y0), float(r), confidence=0.55)


def smooth_bar_path(positions, window: int = 5):
    xs = [p.x for p in positions]; ys = [p.y for p in positions]
    out = list(positions); n = len(positions); half = window // 2
    for i in range(n):
        if positions[i].x is None:
            continue
        lo, hi = max(0, i - half), min(n, i + half + 1)
        local_x = [xs[j] for j in range(lo, hi) if xs[j] is not None]
        local_y = [ys[j] for j in range(lo, hi) if ys[j] is not None]
        if local_x:
            out[i] = BarPosition(
                positions[i].frame_index, sum(local_x) / len(local_x),
                sum(local_y) / len(local_y), positions[i].radius,
                positions[i].confidence, is_estimate=True,
            )
    return out


# ---------------------------------------------------------------------------
# 5) Rep detector (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class Rep:
    rep_number: int
    bottom_frame_index: int
    bottom_timestamp_ms: float
    start_frame_index: int
    end_frame_index: int


def detect_reps(frame_indices, timestamps_ms, hip_y, fps, min_rep_duration_s=0.8, prominence_frac=0.15):
    n = len(hip_y)
    if n == 0:
        return []
    y = np.array([v if v is not None else np.nan for v in hip_y], dtype=float)
    valid = ~np.isnan(y)
    if valid.sum() < 2:
        return []
    idx = np.arange(n)
    y_interp = np.interp(idx, idx[valid], y[valid])
    y_range = float(np.nanmax(y_interp) - np.nanmin(y_interp))
    if y_range < 1e-6:
        return []
    min_distance = max(1, int(min_rep_duration_s * fps))
    prominence = max(1.0, y_range * prominence_frac)
    peaks, _ = find_peaks(y_interp, distance=min_distance, prominence=prominence)
    reps = []
    for i, p in enumerate(peaks):
        start = 0 if i == 0 else (peaks[i - 1] + p) // 2
        end = (n - 1) if i == len(peaks) - 1 else (p + peaks[i + 1]) // 2
        reps.append(Rep(i + 1, int(frame_indices[p]), float(timestamps_ms[p]), int(frame_indices[start]), int(frame_indices[end])))
    return reps


# ---------------------------------------------------------------------------
# 6) Annotator (unchanged: solid green = observed, dashed orange = estimate)
# ---------------------------------------------------------------------------

OBSERVED_COLOR = (60, 220, 60)
ESTIMATE_COLOR = (0, 165, 255)
BOTTOM_MARK_COLOR = (60, 60, 230)
TEXT_COLOR = (255, 255, 255)
SKELETON_EDGES = [("shoulder", "hip"), ("hip", "knee"), ("knee", "ankle"), ("ankle", "foot_index"), ("ear", "shoulder")]


def draw_skeleton(frame, landmarks, side, vis_threshold=0.5):
    def pt(name):
        p = landmarks.get(f"{side}_{name}")
        return p if (p and p.is_visible(vis_threshold)) else None

    for a_name, b_name in SKELETON_EDGES:
        a, b = pt(a_name), pt(b_name)
        if a and b:
            cv2.line(frame, (int(a.x), int(a.y)), (int(b.x), int(b.y)), OBSERVED_COLOR, 2, cv2.LINE_AA)
    for name in ["shoulder", "hip", "knee", "ankle", "foot_index", "ear"]:
        p = pt(name)
        if p:
            cv2.circle(frame, (int(p.x), int(p.y)), 4, OBSERVED_COLOR, -1, cv2.LINE_AA)


def draw_bar_trail(frame, trail_xy, current_radius):
    pts = [(int(x), int(y)) for x, y in trail_xy if x is not None]
    for i in range(1, len(pts)):
        if i % 2 == 0:
            cv2.line(frame, pts[i - 1], pts[i], ESTIMATE_COLOR, 2, cv2.LINE_AA)
    if pts:
        r = int(current_radius) if current_radius else 8
        cv2.circle(frame, pts[-1], r, ESTIMATE_COLOR, 2, cv2.LINE_AA)
        cv2.putText(frame, "bar (est.)", (pts[-1][0] + 10, pts[-1][1]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, ESTIMATE_COLOR, 1, cv2.LINE_AA)


def draw_hud(frame, rep_number, depth_status, is_bottom_frame):
    h, w = frame.shape[:2]
    y = 28
    if rep_number is not None:
        cv2.putText(frame, f"Rep {rep_number}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 2, cv2.LINE_AA)
        y += 26
    if depth_status is not None:
        color = {
            "meets_standard": OBSERVED_COLOR,
            "does_not_meet_standard": (60, 60, 230),
            "cannot_assess": (180, 180, 180),
        }.get(depth_status, TEXT_COLOR)
        cv2.putText(frame, f"Depth: {depth_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        y += 24
    if is_bottom_frame:
        cv2.putText(frame, "BOTTOM", (w - 130, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BOTTOM_MARK_COLOR, 2, cv2.LINE_AA)
        cv2.rectangle(frame, (2, 2), (w - 3, h - 3), BOTTOM_MARK_COLOR, 3)


def legend(frame):
    h, w = frame.shape[:2]
    y = h - 44
    cv2.putText(frame, "solid green = observed landmark", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, OBSERVED_COLOR, 1, cv2.LINE_AA)
    cv2.putText(frame, "dashed orange = estimated bar position", (10, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, ESTIMATE_COLOR, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# 7) LLM assessment agent (unchanged system prompt/contract) -- Groq client is
#    built lazily so importing this module never requires a network call.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the assessment stage of a squat-analysis application.
You receive two JSON objects: SKILL (the document-derived rules you must apply)
and VIDEO_DATA (per-rep measurements from a pose/bar-tracking model). Your job
is to output structured findings, not general fitness advice.

Hard rules:
1. Use ONLY the rules in SKILL. Never invent a threshold, number, or standard
   that is not stated in SKILL. If SKILL does not specify a numeric threshold
   for something, say so and assess qualitatively/directionally only.
2. For every criterion in SKILL, for every rep in VIDEO_DATA, produce exactly
   one finding with this schema:
   {
     "rep_number": int,
     "criterion_id": str,          // must match SKILL criteria[].id
     "criterion": str,             // human-readable name
     "source_pages": [int, ...],   // copy from SKILL for that criterion
     "result": "meets_standard" | "does_not_meet_standard" | "cannot_assess",
     "timestamp_or_frame": number or null,
     "observed_measurement": string or null,   // plain-language, cite the actual numbers used
     "explanation": string,
     "feedback": string,            // actionable, grounded in the SKILL rule text; empty if meets_standard or cannot_assess
     "uncertainty": string          // note tracking confidence, occlusion, or view-angle limits that affect this finding; empty string if none
   }
3. Output "cannot_assess" whenever any of the following is true, and explain
   which one in "uncertainty":
   - assessable_from_side_view for that criterion is false,
   - assessable_from_side_view is "partial" AND the relevant tracking_confidence
     is below 0.5, or the needed measurement is null/empty,
   - assessable_from_side_view is true but the relevant tracking_confidence for
     that rep is below 0.5, or the needed measurement is null/empty/occluded.
4. An unassessable result is preferable to invented precision. Do not guess a
   number that was not provided.
5. Return ONLY a single JSON object: {"overall_summary": string, "findings": [...]}.
   No prose outside the JSON.
"""

_groq_client = None
_groq_model = None


def get_groq_client_and_model():
    """Lazily build the Groq client and auto-pick a model the key has access to
    (unchanged logic from the notebook), caching both for the life of the process."""
    global _groq_client, _groq_model
    if _groq_client is not None:
        return _groq_client, _groq_model

    if not GROQ_API_KEY:
        raise RuntimeError(
            "No Groq API key set. Paste your key (starts with gsk_) into "
            "GROQ_API_KEY_IN_CODE near the top of model.py."
        )

    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    if GROQ_MODEL_OVERRIDE:
        _groq_client, _groq_model = client, GROQ_MODEL_OVERRIDE
        return _groq_client, _groq_model

    preferred = [
        "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant", "openai/gpt-oss-20b",
    ]
    try:
        available = [m.id for m in client.models.list().data]
    except Exception as exc:
        raise RuntimeError(
            f"Groq rejected the API key or could not be reached ({exc}). "
            "Create a new key at https://console.groq.com/keys and paste it into "
            "GROQ_API_KEY_IN_CODE near the top of model.py."
        )

    model = next((m for m in preferred if m in available), (available[0] if available else None))
    if model is None:
        raise RuntimeError("No Groq models are available to this API key. Check your key at console.groq.com/keys.")

    _groq_client, _groq_model = client, model
    print("Using Groq model:", _groq_model)
    return _groq_client, _groq_model


def assess_video(skill: dict, video_data: dict, model: str = None) -> dict:
    client, default_model = get_groq_client_and_model()
    model = model or default_model
    user_payload = {"SKILL": skill, "VIDEO_DATA": video_data}
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    )
    raw = resp.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("WARNING: model did not return valid JSON. Raw output below:")
        print(raw)
        raise


# ---------------------------------------------------------------------------
# 8) THE CONNECTION: build Model 2's input contract from Model 1's real
#    per-rep measurements (unchanged)
# ---------------------------------------------------------------------------

def _pt(landmarks, side, name):
    return landmarks.get(f"{side}_{name}")


def _norm_y(point, frame_h):
    return (point.y / frame_h) if (point is not None and frame_h) else None


def _sample_series(frames_landmarks, bar_positions, side, frame_range, frame_h, kind, n_samples=3):
    """Sample a small series of values across frame_range (inclusive), evenly spaced.
    kind: 'hip_y' | 'shoulder_y' | 'bar_dev_px'."""
    lo, hi = frame_range
    if hi <= lo:
        idxs = [lo]
    else:
        step = max(1, (hi - lo) // max(1, n_samples - 1))
        idxs = list(range(lo, hi + 1, step))[:n_samples]
    out = []
    for i in idxs:
        if i < 0 or i >= len(frames_landmarks):
            continue
        fl = frames_landmarks[i]
        if kind in ("hip_y", "shoulder_y"):
            p = _pt(fl.points, side, "hip" if kind == "hip_y" else "shoulder")
            if p is not None and p.is_visible(CONFIDENCE_FLOOR):
                out.append(round(p.y / frame_h, 4))
        elif kind == "bar_dev_px":
            ankle = _pt(fl.points, side, "ankle")
            toe = _pt(fl.points, side, "foot_index")
            bar = bar_positions[i] if i < len(bar_positions) else None
            if ankle is not None and ankle.is_visible(CONFIDENCE_FLOOR) and bar is not None and bar.x is not None:
                dev = bar_horizontal_deviation_from_midfoot(bar.x, ankle, toe)
                if dev is not None:
                    out.append(round(dev, 1))
    return out


def build_video_data(video_id, fps, side, frames_landmarks, bar_positions, reps, frame_h):
    reps_payload = []
    for rep in reps:
        bottom_idx = rep.bottom_frame_index
        if bottom_idx >= len(frames_landmarks):
            continue
        landmarks = frames_landmarks[bottom_idx].points
        shoulder = _pt(landmarks, side, "shoulder")
        hip = _pt(landmarks, side, "hip")
        knee = _pt(landmarks, side, "knee")
        ankle = _pt(landmarks, side, "ankle")
        toe = _pt(landmarks, side, "foot_index")
        ear = _pt(landmarks, side, "ear")
        bar_at_bottom = bar_positions[bottom_idx] if bottom_idx < len(bar_positions) else None

        hip_angle = joint_angle_deg(shoulder, hip, knee) if (shoulder and hip and knee) else None
        knee_ang = knee_angle_deg(hip, knee, ankle) if (hip and knee and ankle) else None
        back_ang = back_angle_deg(shoulder, hip) if (shoulder and hip) else None
        head_neck_ang = joint_angle_deg(ear, shoulder, hip) if (ear and shoulder and hip) else None

        bar_dev_px = None
        if bar_at_bottom is not None and bar_at_bottom.x is not None and ankle is not None:
            bar_dev_px = bar_horizontal_deviation_from_midfoot(bar_at_bottom.x, ankle, toe)

        knee_forward_px = knee_toe_horizontal_offset_px(knee, toe) if (knee and toe) else None

        ascent_end = min(rep.end_frame_index, bottom_idx + max(1, (rep.end_frame_index - bottom_idx) // 5))
        hip_traj = _sample_series(frames_landmarks, bar_positions, side, (bottom_idx, ascent_end), frame_h, "hip_y")
        shoulder_traj = _sample_series(frames_landmarks, bar_positions, side, (bottom_idx, ascent_end), frame_h, "shoulder_y")
        bar_series = _sample_series(frames_landmarks, bar_positions, side, (rep.start_frame_index, rep.end_frame_index), frame_h, "bar_dev_px", n_samples=5)

        tracking_confidence = {
            "hip": round(float(hip.visibility), 2) if hip else 0.0,
            "knee": round(float(knee.visibility), 2) if knee else 0.0,
            "ankle": round(float(ankle.visibility), 2) if ankle else 0.0,
            "bar": round(float(bar_at_bottom.confidence), 2) if bar_at_bottom else 0.0,
            "shoulder": round(float(shoulder.visibility), 2) if shoulder else 0.0,
        }
        occlusion_flags = [f"{k}_low_confidence" for k, v in tracking_confidence.items() if v < CONFIDENCE_FLOOR]
        if bar_at_bottom is None or bar_at_bottom.x is None:
            occlusion_flags.append("bar_not_detected_at_bottom_frame")

        reps_payload.append({
            "rep_number": rep.rep_number,
            "bottom_frame": bottom_idx,
            "bottom_timestamp_s": round(rep.bottom_timestamp_ms / 1000.0, 2),
            "measurements": {
                "hip_angle_deg": round(hip_angle, 1) if hip_angle is not None else None,
                "knee_angle_deg": round(knee_ang, 1) if knee_ang is not None else None,
                "back_angle_deg": round(back_ang, 1) if back_ang is not None else None,
                "hip_joint_y_norm": round(_norm_y(hip, frame_h), 4) if hip and hip.is_visible(CONFIDENCE_FLOOR) else None,
                "top_of_patella_y_norm": round(_norm_y(knee, frame_h), 4) if knee and knee.is_visible(CONFIDENCE_FLOOR) else None,
                "bar_x_offset_from_midfoot_px": round(bar_dev_px, 1) if bar_dev_px is not None else None,
                "bar_x_offset_series_px": bar_series,
                "knee_forward_of_toe_px": round(knee_forward_px, 1) if knee_forward_px is not None else None,
                "head_neck_angle_deg": round(head_neck_ang, 1) if head_neck_ang is not None else None,
                "hip_y_trajectory_first_20pct": hip_traj,
                "shoulder_y_trajectory_first_20pct": shoulder_traj,
                "bar_height_on_back_norm": None,  # requires a rear view; not measurable from this side-view pipeline
            },
            "tracking_confidence": tracking_confidence,
            "occlusion_flags": occlusion_flags,
        })

    return {"video_id": video_id, "fps": fps, "reps": reps_payload}


# ---------------------------------------------------------------------------
# 9) Combined pipeline: pose + bar tracking + rep detection -> build_video_data
#    -> LLM assessment -> annotated video.
#
#    run_combined_pipeline() is a thin wrapper that ALWAYS releases the video
#    reader/writer, even when something fails. On Windows an open
#    VideoWriter keeps annotated_output.mp4 locked, which used to make the
#    temp-folder cleanup crash and hide the real error.
# ---------------------------------------------------------------------------

def run_combined_pipeline(*args, **kwargs):
    resources = []
    try:
        return _run_combined_pipeline_impl(*args, resources=resources, **kwargs)
    finally:
        for r in resources:
            try:
                r.release()
            except Exception:
                pass


def _run_combined_pipeline_impl(input_video_path, output_video_path, skill, max_duration_s=MAX_DURATION_S_DEFAULT,
                                on_progress=None, resources=None):
    def progress(stage, label):
        print(f"[{stage}] {label}")
        if on_progress:
            on_progress(stage, label)

    # Fail fast on a missing/invalid Groq key, BEFORE minutes of video processing.
    get_groq_client_and_model()

    cap = cv2.VideoCapture(input_video_path)
    if resources is not None:
        resources.append(cap)
    if not cap.isOpened():
        raise RuntimeError("Could not open video file. Check the format is supported (mp4/mov/avi with a standard codec).")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_s = frame_count / fps if fps > 0 else 0.0
    if duration_s > max_duration_s:
        raise RuntimeError(f"Video is {duration_s:.0f}s, exceeds the {max_duration_s}s limit. Trim to a single set.")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))
    if resources is not None:
        resources.append(writer)

    frames_landmarks = []
    bar_positions = []
    buffered = []

    progress("processing_pose", "Running pose detection")
    with PoseProcessor() as pose_proc:
        frame_idx = 0
        prev_bar = None
        side_votes = {"left": 0, "right": 0}
        while True:
            ok, frame_bgr = cap.read()
            if not ok or frame_idx >= TARGET_MAX_FRAMES:
                break
            timestamp_ms = int((frame_idx / fps) * 1000)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            fl = pose_proc.process_frame(frame_rgb, frame_idx, timestamp_ms)
            frames_landmarks.append(fl)
            if fl.detected:
                s = pick_side(fl)
                side_votes[s] += 1
                shoulder = fl.get(f"{s}_shoulder"); hip = fl.get(f"{s}_hip")
                bar_pos = detect_bar_in_frame(frame_bgr, frame_idx, shoulder, hip, prev_bar)
                prev_bar = bar_pos
            else:
                bar_pos = BarPosition(frame_idx, None, None, None, confidence=0.0)
            bar_positions.append(bar_pos)
            buffered.append(frame_bgr)
            frame_idx += 1
            if frame_idx % 60 == 0:
                print(f"  ...{frame_idx} frames processed")
    cap.release()

    if not frames_landmarks:
        raise RuntimeError("No frames could be read from the video.")

    side = "left" if side_votes["left"] >= side_votes["right"] else "right"
    detection_rate = sum(1 for f in frames_landmarks if f.detected) / len(frames_landmarks)
    low_quality_warning = None
    if detection_rate < 0.5:
        low_quality_warning = (
            f"A person was only detected in {detection_rate:.0%} of frames. "
            f"Usually means the camera isn't a clean side view, the lifter is too small/far in frame, "
            f"or lighting/occlusion is poor. 'cannot_assess' results below are expected under these conditions."
        )

    progress("processing_pose", "Smoothing bar path & detecting reps")
    bar_positions = smooth_bar_path(bar_positions)
    hip_y_series = [
        (fl.get(f"{side}_hip").y if (fl.get(f"{side}_hip") and fl.get(f"{side}_hip").is_visible(0.4)) else None)
        for fl in frames_landmarks
    ]
    frame_indices = [f.frame_index for f in frames_landmarks]
    timestamps_ms = [f.timestamp_ms for f in frames_landmarks]
    reps = detect_reps(frame_indices, timestamps_ms, hip_y_series, fps=fps)

    if not reps:
        raise RuntimeError("No reps were detected. Check that the video shows the full up-down motion of at least one squat.")

    progress("assessing", f"Found {len(reps)} rep(s). Building measurement contract")
    video_id = os.path.basename(input_video_path)
    video_data = build_video_data(video_id, float(fps), side, frames_landmarks, bar_positions, reps, h)

    _, groq_model = get_groq_client_and_model()
    progress("assessing", f"Calling the LLM assessment agent ({groq_model})")
    assessment = assess_video(skill, video_data)
    findings = assessment.get("findings", [])
    overall_summary = assessment.get("overall_summary", "")

    # Depth verdict per bottom frame, for the HUD overlay.
    bottom_status_by_frame = {}
    for f in findings:
        if f.get("criterion_id") == "depth":
            for rep in reps:
                if rep.rep_number == f.get("rep_number"):
                    bottom_status_by_frame[rep.bottom_frame_index] = f.get("result")

    progress("annotating", "Rendering annotated video")
    rep_bottom_frames = {r.bottom_frame_index: r.rep_number for r in reps}
    rep_number_by_frame = {}
    for rep in reps:
        for fi in range(rep.start_frame_index, rep.end_frame_index + 1):
            rep_number_by_frame[fi] = rep.rep_number

    trail = []
    TRAIL_LEN = 45
    for i, frame_bgr in enumerate(buffered):
        fl = frames_landmarks[i]
        bar_pos = bar_positions[i]
        trail.append((bar_pos.x, bar_pos.y))
        if len(trail) > TRAIL_LEN:
            trail.pop(0)
        if fl.detected:
            draw_skeleton(frame_bgr, fl.points, side)
        visible_trail = [(x, y) for x, y in trail if x is not None]
        if visible_trail:
            draw_bar_trail(frame_bgr, visible_trail, bar_pos.radius)
        draw_hud(frame_bgr, rep_number_by_frame.get(i), bottom_status_by_frame.get(i), i in rep_bottom_frames)
        legend(frame_bgr)
        writer.write(frame_bgr)
    writer.release()

    return {
        "fps": float(fps), "frame_count": len(frames_landmarks), "duration_s": float(duration_s), "side_used": side,
        "reps": reps, "video_data": video_data, "overall_summary": overall_summary, "findings": findings,
        "annotated_video_path": output_video_path, "low_quality_warning": low_quality_warning,
    }


# ---------------------------------------------------------------------------
# 10) MongoDB / GridFS I/O layer -- replaces Colab's file-upload cell and the
#     local findings.json / video_data.json cells.
# ---------------------------------------------------------------------------

def get_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]


@contextmanager
def _safe_tempdir():
    """Temp folder that never crashes on cleanup (Windows can hold file locks
    a moment longer than Python expects; Python 3.9 has no ignore_cleanup_errors)."""
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def download_video_from_gridfs(db, gridfs_file_id, dest_path):
    fs = GridFS(db, collection=GRIDFS_BUCKET)
    file_id = gridfs_file_id if isinstance(gridfs_file_id, ObjectId) else ObjectId(gridfs_file_id)
    grid_out = fs.get(file_id)
    with open(dest_path, "wb") as f:
        f.write(grid_out.read())
    return dest_path


def upload_video_to_gridfs(db, local_path, filename, content_type="video/mp4"):
    fs = GridFS(db, collection=GRIDFS_BUCKET)
    with open(local_path, "rb") as f:
        return fs.put(f, filename=filename, content_type=content_type)


def reencode_h264_if_possible(path):
    """Best effort: browsers (Chrome/Edge) usually can't play OpenCV's 'mp4v'
    codec. If ffmpeg is installed, re-encode to H.264 so the results page can
    play the annotated video. If ffmpeg is missing, the file is left as-is."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("NOTE: ffmpeg not found -- annotated video stays in mp4v (may not play in some browsers).")
        return
    out_path = path + ".h264.mp4"
    try:
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", path,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
            check=True,
        )
        os.replace(out_path, path)
        print("Annotated video re-encoded to H.264.")
    except Exception as exc:
        print(f"NOTE: ffmpeg re-encode failed ({exc}); keeping original annotated video.")
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass


def update_job(jobs_col, job_id, **fields):
    jobs_col.update_one({"_id": job_id}, {"$set": fields})


def findings_table(findings) -> pd.DataFrame:
    """Same table the notebook displayed (cell 14), unchanged -- just printed
    to the console instead of shown with IPython's display()."""
    df = pd.DataFrame(findings)
    cols = [
        "rep_number", "criterion", "result", "timestamp_or_frame",
        "observed_measurement", "explanation", "feedback", "uncertainty",
        "source_pages",
    ]
    return df[[c for c in cols if c in df.columns]]


def print_findings_table(overall_summary: str, findings: list):
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 40)
    pd.set_option("display.width", 220)
    print(f"\n{'='*70}\nOverall summary (LLM assessment agent)\n{'='*70}")
    print(overall_summary)
    print(f"\n{'='*70}\nFindings (LLM assessment agent, grounded in SQUAT_SKILL)\n{'='*70}")
    print(findings_table(findings).to_string(index=False))


def process_job(jobs_col, db, job: dict):
    """Runs the full pipeline for one job document and writes results back."""
    job_id = job["_id"]
    job_id_str = job.get("job_id", str(job_id))
    print(f"\n=== Processing job {job_id_str} ===")

    update_job(jobs_col, job_id, status="processing", stage="processing_pose",
               stage_label="Running pose detection", error=None)

    with _safe_tempdir() as tmp_dir:
        input_path = os.path.join(tmp_dir, "input_video.mp4")
        output_path = os.path.join(tmp_dir, "annotated_output.mp4")

        download_video_from_gridfs(db, job["gridfs_file_id"], input_path)

        max_duration_s = job.get("model_video_window_seconds") or MAX_DURATION_S_DEFAULT

        def on_progress(stage, label):
            update_job(jobs_col, job_id, stage=stage, stage_label=label)

        result = run_combined_pipeline(
            input_path, output_path, SQUAT_SKILL,
            max_duration_s=max_duration_s, on_progress=on_progress,
        )

        update_job(jobs_col, job_id, stage="saving", stage_label="Saving results")
        reencode_h264_if_possible(output_path)
        annotated_filename = f"annotated_{job.get('original_filename') or (job_id_str + '.mp4')}"
        annotated_gridfs_id = upload_video_to_gridfs(db, output_path, annotated_filename)

        results_payload = {
            "overall_summary": result["overall_summary"],
            "findings": result["findings"],
            "video_data": result["video_data"],
            "low_quality_warning": result["low_quality_warning"],
            "side_used": result["side_used"],
            "fps": result["fps"],
            "frame_count": result["frame_count"],
            "duration_s": result["duration_s"],
            # Stored as a string: a raw ObjectId can't be turned into JSON by the API.
            "annotated_gridfs_file_id": str(annotated_gridfs_id),
            "annotated_filename": annotated_filename,
            # Relative path -- the React app adds the backend address itself.
            # Served by GET /api/videos/{file_id} in main.py.
            "video_url": f"/api/videos/{annotated_gridfs_id}",
        }

        update_job(
            jobs_col, job_id,
            status="done", stage="done",
            stage_label="Analysis complete",
            results=results_payload,
            error=None,
        )
        print(f"=== Job {job_id_str} completed ({len(result['findings'])} findings) ===")
        print_findings_table(result["overall_summary"], result["findings"])


def process_job_by_id(job_identifier: str):
    """Process a single job. job_identifier can match either _id (ObjectId) or
    the job's own job_id string field."""
    db = get_db()
    jobs_col = db[MONGO_COLLECTION_NAME]

    query = {"job_id": job_identifier}
    try:
        query = {"$or": [{"job_id": job_identifier}, {"_id": ObjectId(job_identifier)}]}
    except Exception:
        pass

    job = jobs_col.find_one(query)
    if not job:
        raise RuntimeError(f"No job found matching '{job_identifier}'")

    try:
        process_job(jobs_col, db, job)
    except Exception as exc:
        traceback.print_exc()
        update_job(
            jobs_col, job["_id"],
            status="error", stage="error",
            stage_label="Processing failed",
            error=str(exc),
        )
        raise


def watch_for_jobs():
    """Polls MongoDB forever for jobs that are uploaded and not yet processed."""
    db = get_db()
    jobs_col = db[MONGO_COLLECTION_NAME]
    print(f"Watching '{MONGO_DB_NAME}.{MONGO_COLLECTION_NAME}' for new jobs (Ctrl+C to stop)...")
    while True:
        job = jobs_col.find_one({"stage": "uploaded", "status": {"$in": ["processing", "queued", "pending"]}})
        if job is None:
            time.sleep(POLL_INTERVAL_S)
            continue
        try:
            process_job(jobs_col, db, job)
        except Exception as exc:
            traceback.print_exc()
            print(f"Job {job.get('job_id')} failed: {exc}")
            # Mark it failed so it isn't left stuck as "processing" and the UI can show the error.
            update_job(
                jobs_col, job["_id"],
                status="error", stage="error",
                stage_label="Processing failed",
                error=str(exc),
            )
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Squat-check local worker (MongoDB in/out).")
    parser.add_argument("--job-id", help="Process a single job by job_id or _id, then exit.")
    parser.add_argument("--watch", action="store_true", help="Poll MongoDB forever for new uploaded jobs.")
    args = parser.parse_args()

    if not GROQ_API_KEY and not GROQ_MODEL_OVERRIDE:
        print("WARNING: no Groq API key found. Paste it into GROQ_API_KEY_IN_CODE near the top of model.py.")

    if args.job_id:
        process_job_by_id(args.job_id)
    elif args.watch:
        watch_for_jobs()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()