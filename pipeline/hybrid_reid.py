"""
Hybrid Re-ID: Combines Torso HSV + LAB embeddings for robust visitor matching.
- Torso HSV: Fast, deterministic, lighting-invariant on clothing
- LAB embeddings: Semantic color space for cross-camera matching
"""

import numpy as np
from collections import OrderedDict
from datetime import datetime, timedelta
import cv2
from sklearn.metrics.pairwise import cosine_similarity

class HybridReIDManager:
    def __init__(self, reentry_window_s: int = 300, hsv_weight: float = 0.6, lab_weight: float = 0.4):
        """
        Args:
            reentry_window_s: Time to keep descriptors for re-entry matching
            hsv_weight: Weight for torso HSV histogram similarity
            lab_weight: Weight for LAB color embeddings
        """
        self.reentry_window_s = reentry_window_s
        self.hsv_weight = hsv_weight
        self.lab_weight = lab_weight
        self.gallery = OrderedDict()  # {visitor_id: (timestamp, hsv_hist, lab_embedding)}
        
    def extract_torso_hsv(self, frame: np.ndarray, bbox: tuple) -> np.ndarray:
        """
        Extract HSV histogram from torso region (lower 60% of bbox).
        Fast, lighting-invariant descriptor for clothing.
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h = y2 - y1
        torso_y1 = y1 + int(h * 0.4)  # Skip head, focus on clothes
        torso_region = frame[torso_y1:y2, x1:x2]
        
        if torso_region.size == 0:
            return np.zeros(256)  # 256-bin HSV histogram
        
        hsv = cv2.cvtColor(torso_region, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        return hist
    
    def extract_lab_embedding(self, frame: np.ndarray, bbox: tuple) -> np.ndarray:
        """
        Extract 96-dim LAB color embedding from entire bbox.
        Robust cross-camera descriptor.
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        roi = frame[y1:y2, x1:x2]
        
        if roi.size == 0:
            return np.zeros(96)
        
        # Convert to LAB
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        
        # Compute 96-dim histogram (4x4x6 for L*a*b quantization)
        lab_hist = np.histogramdd(
            lab.reshape(-1, 3),
            bins=[4, 8, 12],
            range=[[0, 256], [0, 256], [0, 256]]
        )[0]
        lab_embedding = lab_hist.flatten() / (lab_hist.sum() + 1e-8)
        return lab_embedding
    
    def match_visitor(self, frame: np.ndarray, bbox: tuple, max_candidates: int = 5) -> tuple:
        """
        Match against gallery. Returns (visitor_id, confidence).
        Confidence = hsv_weight * hsv_sim + lab_weight * lab_sim
        """
        hsv_hist = self.extract_torso_hsv(frame, bbox)
        lab_emb = self.extract_lab_embedding(frame, bbox)
        
        if not self.gallery:
            return None, 0.0
        
        scores = []
        now = datetime.now()
        
        for visitor_id, (ts, old_hsv, old_lab) in list(self.gallery.items())[-max_candidates:]:
            # Age decay: older matches get lower scores
            age_s = (now - ts).total_seconds()
            if age_s > self.reentry_window_s:
                continue
            
            age_factor = 1.0 - (age_s / self.reentry_window_s) * 0.3
            
            # Similarities
            hsv_sim = float(cv2.compareHist(hsv_hist, old_hsv, cv2.HISTCMP_COSINE))
            lab_sim = cosine_similarity([lab_emb], [old_lab])[0, 0]
            
            combined_score = (self.hsv_weight * hsv_sim + self.lab_weight * lab_sim) * age_factor
            scores.append((visitor_id, combined_score))
        
        if scores:
            best_visitor, best_score = max(scores, key=lambda x: x[1])
            return best_visitor if best_score >= 0.75 else None, best_score
        
        return None, 0.0
    
    def add_to_gallery(self, visitor_id: str, frame: np.ndarray, bbox: tuple) -> None:
        """Store descriptors for future re-entry matching."""
        hsv_hist = self.extract_torso_hsv(frame, bbox)
        lab_emb = self.extract_lab_embedding(frame, bbox)
        self.gallery[visitor_id] = (datetime.now(), hsv_hist, lab_emb)
        
        # Evict old entries
        while len(self.gallery) > 1000:
            self.gallery.popitem(last=False)
    
    def evict_expired(self) -> None:
        """Remove stale entries from gallery."""
        now = datetime.now()
        expired = [
            vid for vid, (ts, _, _) in self.gallery.items()
            if (now - ts).total_seconds() > self.reentry_window_s
        ]
        for vid in expired:
            del self.gallery[vid]
