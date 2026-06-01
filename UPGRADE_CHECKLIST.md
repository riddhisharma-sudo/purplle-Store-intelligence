# Detection Layer Upgrade Checklist

## Phase 1: Model (30 min)
- [ ] Update `detect.py` line 266: `yolov8s.pt` → `yolov8m.pt`
- [ ] Test inference speed: `python -m pipeline.detect --model yolov8m.pt --conf 0.35`
- [ ] Verify mAP improvement on test clips

## Phase 2: Hybrid Re-ID (2 hours)
- [ ] Create `pipeline/hybrid_reid.py`
- [ ] Implement `HybridReIDManager` class
- [ ] Update `process_clip()` to use new manager
- [ ] Test re-entry detection: compare old vs new method

## Phase 3: Advanced Staff Detection (1.5 hours)
- [ ] Create `pipeline/advanced_staff_detector.py`
- [ ] Implement HSV uniform detection
- [ ] Implement zone traversal heuristic
- [ ] Calibrate thresholds on labeled test data

## Phase 4: Kafka Integration (1 hour)
- [ ] Create `pipeline/kafka_emitter.py`
- [ ] Add Kafka/Redis dependencies
- [ ] Update `EventEmitter` to use new backend
- [ ] Test fallback mechanism

## Phase 5: Integration & Testing (2 hours)
- [ ] Update all imports in `detect.py`
- [ ] Run on real CCTV clips
- [ ] Validate event schemas
- [ ] Compare metrics before/after

## Phase 6: Documentation (30 min)
- [ ] Write DESIGN.md
- [ ] Add prompt blocks to code
- [ ] Document AI tools used

**Total Time: ~7 hours for production-grade implementation**
