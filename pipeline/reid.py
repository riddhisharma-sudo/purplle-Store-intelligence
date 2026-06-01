"""
pipeline/reid.py
────────────────
Hybrid Re-Identification engine that combines:
  • HSV histogram-based staff filter  (fast, CPU-only)
  • LAB colour-space embedding distance for visitor Re-ID
  • Cross-camera deduplication via a shared ReIDManager instance
  • Re-entry detection (visitor re-enters within TTL window)
  • Weighted confidence score merging both signals

Usage
─────
    manager = ReIDManager(staff_hsv_model_path="data/staff_hsv.json")
    result  = manager.identify(crop_bgr, camera_id="CAM_FLOOR_01")
    # result.visitor_id, result.is_staff, result.is_reentry, result.confidence
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Tunable thresholds ─────────────────────────────────────────────────────────
LAB_COSINE_THRESHOLD   = 0.82   # minimum similarity to call a re-entry match
HSV_CHI_THRESHOLD      = 0.35   # maximum chi² distance to flag as staff uniform
GALLERY_TTL_SECONDS    = 300    # how long exited descriptors are kept
LAB_WEIGHT             = 0.65   # contribution of LAB score to merged confidence
HSV_WEIGHT             = 0.35   # contribution of (inverted) HSV distance


# ══════════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReIDResult:
    visitor_id:  str
    is_staff:    bool
    is_reentry:  bool
    confidence:  float          # 0.0–1.0 merged score


@dataclass
class _GalleryEntry:
    visitor_id:  str
    descriptor:  np.ndarray     # L1-normalised 96-dim LAB histogram
    timestamp:   float          # unix time of last sighting
    camera_id:   str


# ══════════════════════════════════════════════════════════════════════════════
# LAB descriptor helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_lab_histogram(bgr_crop: np.ndarray) -> np.ndarray:
    """
    Build a 96-dim LAB colour histogram from a bounding-box crop.

    Channel bins: L→32, A→32, B→32.
    Vectors are L2-normalised so cosine similarity == dot product.
    """
    if bgr_crop is None or bgr_crop.size == 0:
        return np.zeros(96, dtype=np.float32)

    lab = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2LAB)

    hist_l = cv2.calcHist([lab], [0], None, [32], [0, 256]).flatten()
    hist_a = cv2.calcHist([lab], [1], None, [32], [0, 256]).flatten()
    hist_b = cv2.calcHist([lab], [2], None, [32], [0, 256]).flatten()

    descriptor = np.concatenate([hist_l, hist_a, hist_b]).astype(np.float32)

    # ── L2 normalisation (unit vector → cosine sim = dot product) ─────────────
    norm = np.linalg.norm(descriptor)
    if norm > 1e-6:
        descriptor /= norm

    return descriptor


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Dot product of two L2-normalised vectors (equivalent to cosine similarity)."""
    return float(np.dot(a, b))


# ══════════════════════════════════════════════════════════════════════════════
# HSV staff-filter helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_hsv_histogram(bgr_crop: np.ndarray) -> np.ndarray:
    """
    Extract an HSV histogram from the lower 2/3 of the bounding box
    (clothing region) — 64 H-bins, 32 S-bins → 96 dims.
    Normalised to [0, 1].
    """
    if bgr_crop is None or bgr_crop.size == 0:
        return np.zeros(96, dtype=np.float32)

    h, w = bgr_crop.shape[:2]
    clothing_region = bgr_crop[h // 3:, :]    # lower 2/3 of crop

    hsv = cv2.cvtColor(clothing_region, cv2.COLOR_BGR2HSV)
    hist_h = cv2.calcHist([hsv], [0], None, [64], [0, 180]).flatten()
    hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256]).flatten()

    descriptor = np.concatenate([hist_h, hist_s]).astype(np.float32)
    total = descriptor.sum()
    if total > 0:
        descriptor /= total                    # probability distribution

    return descriptor


def _chi_squared_distance(p: np.ndarray, q: np.ndarray) -> float:
    """
    Chi-squared histogram distance — lower means more similar.
    Handles zero bins safely.
    """
    denom = p + q + 1e-10
    return float(np.sum((p - q) ** 2 / denom))


# ══════════════════════════════════════════════════════════════════════════════
# Main manager
# ══════════════════════════════════════════════════════════════════════════════

class ReIDManager:
    """
    Shared Re-ID manager.  One instance covers all cameras in the same store
    so that cross-camera deduplication works transparently.

    Parameters
    ──────────
    staff_hsv_model_path : path to a JSON file mapping uniform name → HSV
                           histogram list (length 96).  If absent, HSV staff
                           filter is disabled gracefully.
    """

    def __init__(
        self,
        staff_hsv_model_path: Optional[str] = None,
        lab_threshold:   float = LAB_COSINE_THRESHOLD,
        hsv_threshold:   float = HSV_CHI_THRESHOLD,
        gallery_ttl:     float = GALLERY_TTL_SECONDS,
    ) -> None:
        self._lab_threshold  = lab_threshold
        self._hsv_threshold  = hsv_threshold
        self._gallery_ttl    = gallery_ttl

        # Ordered-dict preserves insertion order → easy TTL eviction
        self._gallery: OrderedDict[str, _GalleryEntry] = OrderedDict()
        self._visitor_counter = 0

        # Load staff HSV models
        self._staff_histograms: List[np.ndarray] = []
        if staff_hsv_model_path and Path(staff_hsv_model_path).exists():
            self._load_staff_models(staff_hsv_model_path)

    # ── Public API ─────────────────────────────────────────────────────────────

    def identify(
        self,
        bgr_crop: np.ndarray,
        camera_id: str = "unknown",
    ) -> ReIDResult:
        """
        Main entry point.  Given a bounding-box crop and its source camera,
        returns a ReIDResult with visitor_id, staff flag, re-entry flag,
        and a merged confidence score.
        """
        self._evict_expired()

        # ── Staff detection (fast path) ───────────────────────────────────────
        hsv_hist  = _extract_hsv_histogram(bgr_crop)
        is_staff, hsv_dist = self._is_staff(hsv_hist)

        if is_staff:
            return ReIDResult(
                visitor_id=f"STAFF_{camera_id}",
                is_staff=True,
                is_reentry=False,
                confidence=1.0 - (hsv_dist / self._hsv_threshold),
            )

        # ── Visitor Re-ID (LAB) ───────────────────────────────────────────────
        lab_desc  = _extract_lab_histogram(bgr_crop)
        best_id, lab_similarity = self._match_gallery(lab_desc)

        is_reentry = lab_similarity >= self._lab_threshold
        if is_reentry:
            visitor_id = best_id
        else:
            visitor_id = self._new_visitor_id()

        # ── Merged confidence ─────────────────────────────────────────────────
        # HSV contribution: inverted normalised distance from threshold.
        # LAB contribution: raw cosine similarity (0→1).
        hsv_score = max(0.0, 1.0 - hsv_dist / max(self._hsv_threshold, 1e-6))
        lab_score = max(0.0, lab_similarity)

        merged_confidence = (
            LAB_WEIGHT * lab_score +
            HSV_WEIGHT * hsv_score
        )
        merged_confidence = float(np.clip(merged_confidence, 0.0, 1.0))

        # ── Update gallery ────────────────────────────────────────────────────
        self._gallery[visitor_id] = _GalleryEntry(
            visitor_id=visitor_id,
            descriptor=lab_desc,
            timestamp=time.monotonic(),
            camera_id=camera_id,
        )

        logger.debug(
            "Re-ID: %s | camera=%s | reentry=%s | lab=%.3f | hsv_dist=%.3f | conf=%.3f",
            visitor_id, camera_id, is_reentry, lab_similarity, hsv_dist, merged_confidence,
        )

        return ReIDResult(
            visitor_id=visitor_id,
            is_staff=False,
            is_reentry=is_reentry,
            confidence=merged_confidence,
        )

    def retire_track(self, visitor_id: str) -> None:
        """
        Called when a track is definitively lost or crosses the EXIT line.
        Keeps the descriptor in the gallery for re-entry matching within TTL.
        """
        if visitor_id in self._gallery:
            self._gallery[visitor_id].timestamp = time.monotonic()
            logger.debug("Track retired: %s (held in gallery for re-entry)", visitor_id)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _match_gallery(self, descriptor: np.ndarray) -> Tuple[str, float]:
        """
        Search active gallery for the closest LAB match.
        Returns (visitor_id, cosine_similarity) of the best hit, or ("", 0.0).
        """
        best_id    = ""
        best_score = 0.0

        for vid, entry in self._gallery.items():
            score = _cosine_similarity(descriptor, entry.descriptor)
            if score > best_score:
                best_score = score
                best_id    = vid

        return best_id, best_score

    def _is_staff(self, hsv_hist: np.ndarray) -> Tuple[bool, float]:
        """
        Compare incoming HSV histogram against all loaded staff-uniform models.
        Returns (is_staff, best_chi_squared_distance).
        """
        if not self._staff_histograms:
            return False, float("inf")

        best_dist = min(
            _chi_squared_distance(hsv_hist, model)
            for model in self._staff_histograms
        )
        return best_dist <= self._hsv_threshold, best_dist

    def _new_visitor_id(self) -> str:
        self._visitor_counter += 1
        return f"VIS_{self._visitor_counter:06x}"

    def _evict_expired(self) -> None:
        now = time.monotonic()
        to_remove = [
            vid for vid, entry in self._gallery.items()
            if (now - entry.timestamp) > self._gallery_ttl
        ]
        for vid in to_remove:
            del self._gallery[vid]
            logger.debug("Gallery evicted (TTL): %s", vid)

    def _load_staff_models(self, path: str) -> None:
        try:
            with open(path) as fh:
                data: Dict[str, List[float]] = json.load(fh)
            for name, hist_list in data.items():
                arr = np.array(hist_list, dtype=np.float32)
                total = arr.sum()
                if total > 0:
                    arr /= total
                self._staff_histograms.append(arr)
                logger.info("Loaded staff HSV model: %s (%d bins)", name, len(arr))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load staff HSV models from %s: %s", path, exc)
