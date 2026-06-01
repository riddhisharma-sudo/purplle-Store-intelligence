"""
Advanced Staff Detection: HSV uniform classifier + zone traversal heuristic.
- Phase 1: Detect uniform colors (blue, black, white common for retail)
- Phase 2: If ambiguous, check zone traversal patterns (staff cross many zones quickly)
"""

import cv2
import numpy as np
from collections import defaultdict

class AdvancedStaffDetector:
    def __init__(self, layout_path: str, store_id: str):
        """Initialize with store layout for zone traversal heuristic."""
        self.layout_path = layout_path
        self.store_id = store_id
        self.zone_traversals = defaultdict(list)  # visitor_id -> [zone_ids]
        self.zone_entry_times = defaultdict(list)  # visitor_id -> [timestamps]
        
        # Standard retail uniform HSV ranges (H, S, V)
        self.uniform_ranges = [
            # Black uniform
            {"name": "black", "H": (0, 180), "S": (0, 50), "V": (0, 100)},
            # Navy blue
            {"name": "navy", "H": (100, 130), "S": (50, 255), "V": (50, 150)},
            # White/light
            {"name": "white", "H": (0, 180), "S": (0, 30), "V": (200, 255)},
        ]
    
    def detect_uniform_hsv(self, frame: np.ndarray, bbox: tuple) -> float:
        """
        Detect uniform color in torso region.
        Returns confidence (0-1).
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h = y2 - y1
        torso_region = frame[y1 + int(h*0.3):y1 + int(h*0.7), x1:x2]
        
        if torso_region.size == 0:
            return 0.0
        
        hsv = cv2.cvtColor(torso_region, cv2.COLOR_BGR2HSV)
        
        max_confidence = 0.0
        for uniform in self.uniform_ranges:
            h_range = uniform["H"]
            s_range = uniform["S"]
            v_range = uniform["V"]
            
            mask = cv2.inRange(
                hsv,
                (h_range[0], s_range[0], v_range[0]),
                (h_range[1], s_range[1], v_range[1])
            )
            
            confidence = np.sum(mask > 0) / (torso_region.shape[0] * torso_region.shape[1])
            max_confidence = max(max_confidence, confidence)
        
        return max_confidence
    
    def check_zone_traversal_heuristic(self, visitor_id: str, min_zones: int = 6) -> bool:
        """
        If visitor crossed >60% of distinct zones in <3 minutes → likely staff.
        """
        if visitor_id not in self.zone_traversals:
            return False
        
        zones = self.zone_traversals[visitor_id]
        times = self.zone_entry_times[visitor_id]
        
        if len(zones) < min_zones:
            return False
        
        unique_zones = len(set(zones))
        time_window_s = (times[-1] - times[0]).total_seconds() if len(times) > 1 else 0
        
        # Staff: many unique zones visited quickly
        store_total_zones = 9  # From your layout
        zone_coverage = unique_zones / store_total_zones
        
        return zone_coverage >= 0.6 and time_window_s < 180  # 3 minutes
    
    def is_staff(self, frame: np.ndarray, bbox: tuple, visitor_id: str) -> bool:
        """Combined staff detection."""
        uniform_conf = self.detect_uniform_hsv(frame, bbox)
        traversal_is_staff = self.check_zone_traversal_heuristic(visitor_id)
        
        # If clear uniform match (>70%) → staff
        if uniform_conf > 0.7:
            return True
        
        # If traversal heuristic triggered → staff
        if traversal_is_staff:
            return True
        
        return False
    
    def record_zone_entry(self, visitor_id: str, zone_id: str, timestamp) -> None:
        """Track zone entries for traversal heuristic."""
        self.zone_traversals[visitor_id].append(zone_id)
        self.zone_entry_times[visitor_id].append(timestamp)
