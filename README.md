# 🏬 Store Intelligence System

### **End-to-End Retail Video Analytics & Live Intelligence Platform**

[![Tech Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20PostgreSQL%20%7C%20YOLOv8%20%7C%20Rich-blue)](https://github.com/riddhisharma-sudo/purplle-Store-intelligence)
[![Test Suite](https://img.shields.io/badge/Tests-Pytest%20%3E70%25%20Coverage-green)](pytest.ini)
[![Deployment](https://img.shields.io/badge/Deployed-Render%20%7C%20Live-brightgreen)](https://purplle-store-intelligence-17fl.onrender.com)
[![API Docs](https://img.shields.io/badge/API%20Docs-Swagger%20UI-orange)](https://purplle-store-intelligence-17fl.onrender.com/docs)

The **Store Intelligence System** is an enterprise-grade, edge-to-cloud analytical platform that transforms raw security CCTV footage into real-time retail intelligence. By processing video feeds at the edge, stitching spatial events into logical customer shopping journeys, and correlating physical movements with point-of-sale (POS) data, it opens up the offline retail "black box" to compute the ultimate retail North Star: **Offline Store Conversion Rate**.

---

## 🌐 Live Deployment

| Service | URL |
|---|---|
| **API Root** | https://purplle-store-intelligence-17fl.onrender.com |
| **Interactive Docs** | https://purplle-store-intelligence-17fl.onrender.com/docs |
| **Health Check** | https://purplle-store-intelligence-17fl.onrender.com/health |
| **Store 1 Metrics** | https://purplle-store-intelligence-17fl.onrender.com/stores/STORE_PRP_001/metrics?date=2026-04-10 |
| **Store 2 Metrics** | https://purplle-store-intelligence-17fl.onrender.com/stores/STORE_002/metrics?date=2026-06-01 |

---

## 🗺️ Table of Contents

1. [The Problem](#1-the-problem)
2. [The Solution](#2-the-solution)
3. [Innovation](#3-innovation)
4. [Features](#4-features)
5. [User Journey](#5-user-journey)
6. [System Architecture](#6-system-architecture)
7. [Workflow & Orchestration](#7-workflow--orchestration)
8. [Data Flow & State Management](#8-data-flow--state-management)
9. [Tech Stack](#9-tech-stack)
10. [AI Deep Dive — Gemini 2.5 Flash](#10-ai-deep-dive--gemini-25-flash)
11. [Impact](#11-impact)
12. [Real-World Use Cases](#12-real-world-use-cases)
13. [Comparison](#13-comparison)
14. [Scalability](#14-scalability)
15. [Responsible AI and Ethics](#15-responsible-ai-and-ethics)
16. [Evaluation Criteria Alignment](#16-evaluation-criteria-alignment)
17. [Trade-offs](#17-trade-offs)
18. [Project Complexity Tiers](#18-project-complexity-tiers)
19. [Installation & Setup](#19-installation--setup)
20. [Why This Will Win](#20-why-this-will-win)
21. [Future Scope](#21-future-scope)
22. [FAQ](#22-faq)
23. [Lessons Learned](#23-lessons-learned)

---

## 1. The Problem

Online e-commerce benefits from extensive user tracking tools (e.g., Google Analytics). Merchants can trace mouse heatmaps, track page-to-checkout funnels, log exact dwell times, and immediately measure conversion rates.

In physical retail, however, store managers are historically blind:
* **The Footfall Illusion:** Infrared entry beams only count bulk entrances and exits. They cannot distinguish a family of three from three individual buyers, nor can they tell if a visitor is a store clerk.
* **The Conversion Blindspot:** Managers see total daily sales (POS) and total daily footfall, but cannot correlate the two dynamically. They do not know *which* aisles were browsed, where checkout queues backed up, or why a customer walked out empty-handed.
* **Operational Lag:** Long queues at cash registers cause queue abandonment, but alerts are usually raised manually after customers have already walked out.

---

## 2. The Solution

Our platform solves the offline retail blindspot through a tightly coupled **three-tier system**:

1. **Edge CV Analytics Node (`pipeline/`):** Processes camera feeds locally using an optimized YOLOv8s and ByteTrack configuration. It classifies coordinates against retail zones, filters out store staff, and maps customer identities across camera overlaps using a fast, lighting-invariant Re-ID model.
2. **Asynchronous Intelligence API (`app/`):** A high-performance FastAPI server powered by asynchronous SQLAlchemy and PostgreSQL. It ingests batch events, aggregates spatial trajectories into active shopper sessions, deduplicates transactions, and exposes real-time analytical endpoints. **Deployed live on Render.**
3. **Live TUI Terminal Dashboard (`dashboard/`):** A beautiful real-time Text User Interface (TUI) powered by the `rich` library. It connects to the live API via WebSocket (HTTP-poll fallback) and displays active customer volume, conversion rates, zone heatmaps, checkout funnel drop-offs, and critical system anomalies.

---

## 3. Innovation

This platform introduces several edge-native optimizations designed to eliminate the heavy hardware requirements of standard computer vision pipelines:

* **Dual-Core Staff Shielding:** Rather than deploying slow, resource-heavy Vision-Language Models (VLMs) to identify clerks, we implement a two-stage filter:
  1. *Primary HSV Uniform Detector:* Analyzes the lower 2/3 of a bounding box (clothing region) and compares it against store uniform HSV color models in $<0.5\text{ms}$ on low-end CPUs.
  2. *Contextual Path Heuristic:* If a tracked individual crosses $>60\%$ of distinct store zones within a 3-minute window, they are flagged as staff, retroactively removing them from footfall counts.
* **Lightweight LAB Color Space Re-ID:** Instead of running heavy deep feature extractors (like ResNet or OSNet) at every camera junction, we build a 96-dimensional LAB color histogram. By separating luminance ($L$) from chrominance ($A$ and $B$), the Re-ID algorithm is highly invariant to dynamic store lighting changes and runs in $<1\text{ms}$ per comparison on a single CPU core.
* **Adaptive Frame-Skipping:** Standard pipelines process $15\text{–}30\text{fps}$, bottlenecking CPUs. Since retail shoppers move at slow, predictable speeds, our pipeline runs on a $3\times$ adaptive frame-skip ($5\text{fps}$ effective), maintaining tracking fidelity while reducing compute overhead by $66\%$.

---

## 4. Features

* **Multi-Camera Occlusion-Resistant Tracking:** Integrates ByteTrack's dual-pass association to maintain visitor tracking even through severe billing queue occlusions.
* **Vectorized Polygon Zone Mapping:** Utilizes ray-casting polygon intersection algorithms (`shapely`) to classify bounding box centroids into dynamic store zones (e.g., `ENTRY`, `FLOOR`, `BILLING_QUEUE`, etc.).
* **Idempotent Ingestion Engine with Kafka + Redis Fallback:** Ingests up to 500 events per batch with high-performance deduplication. Publishes to Kafka (primary) with exponential-backoff retry, falling back to Redis Streams if the broker is unavailable.
* **Real-time Session State Machine:** Builds comprehensive visitor histories, accumulating total dwell times and tracking exact zone pathways.
* **Receipt-to-Session Correlation:** Automatically correlates POS transactions with store sessions based on checkout times within a tight 5-minute sliding window.
* **Active Anomaly & Alerts Engine:** Runs background async loops every 30s to trigger, persist, and auto-resolve critical retail issues (e.g., `BILLING_QUEUE_SPIKE`, `CONVERSION_DROP`, `DEAD_ZONE`, `STALE_FEED`).
* **Interactive Live TUI Dashboard:** WebSocket primary feed with HTTP-poll fallback (`DASHBOARD_MODE=TUI`). Features color-coded KPI tiles, conversion funnel bars, zone heatmap, and a severity-coded anomaly log panel.

---

## 5. User Journey

```
[ENTRY CAM]             [FLOOR CAM]              [BILLING CAM]           [POS SYSTEM]
  │                       │                        │                       │
  ├─► Customer enters     │                        │                       │
  │   (ENTRY Event)       │                        │                       │
  │   visitor_id: VIS_104 │                        │                       │
  │                       │                        │                       │
  │                       ├─► Browses cosmetics    │                       │
  │                       │   (ZONE_ENTER: SKINCARE│                       │
  │                       │   Dwells for 4 mins    │                       │
  │                       │                        │                       │
  │                       │                        ├─► Enters checkout queue
  │                       │                        │   (BILLING_QUEUE_JOIN)│
  │                       │                        │   queue_depth checked │
  │                       │                        │                       │
  │                       │                        │                       ├─► Customer pays
  │                       │                        │                       │   POS transaction
  │                       │                        │                       │   (POST /pos/ingest)
  │                       │                        │                       │
  │                       │                        │                       ├─► Match within 5 min
  │                       │                        │                       │   session VIS_104 → converted!
  │                       │                        │                       │
  │                       │                        ├─► Exits register      │
  │                       │                        │   (BILLING_QUEUE_EXIT)│
  │                       │                        │                       │
  ├─► Steps out of store  │                        │                       │
  │   (EXIT Event)        │                        │                       │
  │   Session finalized   │                        │                       │
```

---

## 6. System Architecture
```mermaid
flowchart TD

    subgraph Client["Client Applications"]
        A1["Event Producers"] -->|JSONL Batch| API
        A2["POS Systems"] -->|Transactions| API
        A3["Dashboards"] -->|Metrics/Funnel/Heatmap| API
    end

    subgraph API["FastAPI Application"]
        direction TB
        M["Middleware: Structured Logging + Trace IDs"]
        E["Exception Handlers: Safe JSON Errors"]
        R1["POST /events/ingest"]
        R2["POST /pos/ingest"]
        R3["GET /stores/{id}/metrics"]
        R4["GET /stores/{id}/funnel"]
        R5["GET /stores/{id}/heatmap"]
        R6["GET /stores/{id}/anomalies"]
        R7["GET /health"]
        R8["GET / (root)"]

        M --> E
        E --> R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8
    end

    subgraph DB["Database Layer"]
        D1["PostgreSQL (Primary)"]
        D2["SQLite WAL (Fallback)"]
    end

    subgraph Background["Background Tasks"]
        B1["Anomaly Detection Loop"]
    end

    API --> DB
    API --> Background
    Background --> DB
```
---

## 6a. Detection Pipeline — Frame to Event

```mermaid
flowchart TD

    subgraph Cameras["Camera Feeds"]
        C1["Bounding Box Crops"]
    end

    subgraph Detection["Detection Layer"]
        D1["YOLOv8m Object Detection"]
        D2["ByteTrack Multi‑Object Tracking"]
        C1 --> D1 --> D2
    end

    subgraph ReID["Hybrid Re‑Identification"]
        R1["HSV Staff Filter"]
        R2["LAB Embedding Re‑ID"]
        R3["Cross‑Camera Deduplication"]
        R4["Re‑Entry Detection (TTL)"]
        D2 --> R1 & R2
        R1 & R2 --> R3 --> R4
    end

    subgraph EventStream["Event Stream"]
        E1["Kafka Transport"]
        E2["Redis Streams Fallback"]
        R4 --> E1 --> API
        R4 --> E2 --> API
    end

    subgraph API["FastAPI Application"]
        direction TB
        M["Middleware: Trace Logging"]
        H["Exception Handlers"]
        Ingest["POST /events/ingest"]
        POS["POST /pos/ingest"]
        Metrics["GET /stores/{id}/metrics"]
        Funnel["GET /stores/{id}/funnel"]
        Heatmap["GET /stores/{id}/heatmap"]
        Anomalies["GET /stores/{id}/anomalies"]
        Health["GET /health"]

        M --> H --> Ingest & POS & Metrics & Funnel & Heatmap & Anomalies & Health
    end

    subgraph DB["Database Layer"]
        DB1["PostgreSQL (Primary)"]
        DB2["SQLite WAL (Fallback)"]
    end

    subgraph Background["Background Tasks"]
        B1["Async Anomaly Detection Loop"]
    end

    API --> DB
    API --> Background
    Background --> DB

```

---

## 6b. Session State Machine

```mermaid
stateDiagram-v2
    [*] --> Event
    Event --> Session: ENTRY
    Session --> Zone: ZONE_ENTER / ZONE_DWELL / ZONE_EXIT
    Zone --> Billing: BILLING_QUEUE_JOIN
    Billing --> Billing: BILLING_QUEUE_ABANDON
    Billing --> Session: EXIT
    Session --> Conversion: POS Transaction
    Session --> [*]: Session End

    state Event {
        [*] --> ENTRY
        ENTRY --> EXIT
        ENTRY --> ZONE_ENTER
        ZONE_ENTER --> ZONE_DWELL
        ZONE_DWELL --> ZONE_EXIT
        EXIT --> [*]
    }

    state Session {
        [*] --> Active
        Active --> Converted: converted=True
        Active --> Abandoned: queue_abandoned=True
        Active --> Reentry: is_reentry=True
        Converted --> [*]
        Abandoned --> [*]
        Reentry --> Active
    }

    state Anomaly {
        [*] --> Detected
        Detected --> Resolved
        Resolved --> [*]
    }

```

---

## 6c. Hybrid Re-ID — HSV + LAB Confidence Merge

```mermaid
flowchart LR
    subgraph Input["Bounding Box Crop"]
        I1["BGR Crop"]
    end

    I1 --> HSV["HSV Histogram"]
    I1 --> LAB["LAB Histogram"]

    HSV --> StaffCheck["Staff Filter (Chi² distance ≤ threshold)"]
    LAB --> VisitorMatch["Visitor Re‑ID (Cosine similarity ≥ threshold)"]

    StaffCheck -->|is_staff| ResultStaff["STAFF_xxx"]
    VisitorMatch -->|is_reentry| ResultVisitor["Existing Visitor ID"]
    VisitorMatch -->|new| NewVisitor["New Visitor ID"]

    subgraph Confidence["Confidence Merge"]
        C1["HSV Score = 1 - dist/threshold"]
        C2["LAB Score = cosine similarity"]
        Merge["Weighted Merge: 0.65*LAB + 0.35*HSV"]
    end

    StaffCheck --> C1
    VisitorMatch --> C2
    C1 & C2 --> Merge --> Final["ReIDResult(visitor_id, is_staff, is_reentry, confidence)"]

```

---

## 6d. Kafka + Redis Ingestion with Fallback

```mermaid
flowchart TD
    A["POST /events/ingest\n≤ 500 events"] --> B["Deduplication\ncheck event_id in PostgreSQL"]
    B --> C{"Novel events?"}
    C -->|"All duplicates"| D["Return 202\n0 accepted"]
    C -->|"Novel batch"| E["Kafka Broker\naiokafka producer"]

    E --> F{"Attempt 1"}
    F -->|"Success"| G["bus = kafka\n✅ sent"]
    F -->|"Error"| H["Backoff 0.5s → Attempt 2"]
    H -->|"Success"| G
    H -->|"Error"| I["Backoff 1.0s → Attempt 3"]
    I -->|"Success"| G
    I -->|"Error (exhausted)"| J["Redis Streams Fallback\naioredis XADD\nbus = redis"]

    G & J --> K["Persist to PostgreSQL\ncommit novel events"]
    K -->|"DB error"| L["Return 500\nbus ok but DB failed"]
    K -->|"Success"| M["Return 202\naccepted + bus used\n+ duplicates"]

    J -->|"Redis also fails"| N["Return 503\nboth buses down"]

    %% --- Custom Styles ---
    style A fill:#2563eb,color:#fff,stroke:#1e40af
    style B fill:#38bdf8,color:#000,stroke:#0ea5e9
    style C fill:#facc15,color:#000,stroke:#ca8a04
    style D fill:#9ca3af,color:#000,stroke:#4b5563
    style E fill:#f97316,color:#fff,stroke:#c2410c
    style F fill:#fde68a,color:#000,stroke:#ca8a04
    style G fill:#22c55e,color:#fff,stroke:#15803d
    style H fill:#fcd34d,color:#000,stroke:#b45309
    style I fill:#fbbf24,color:#000,stroke:#92400e
    style J fill:#eab308,color:#000,stroke:#854d0e
    style K fill:#06b6d4,color:#fff,stroke:#0e7490
    style L fill:#ef4444,color:#fff,stroke:#991b1b
    style M fill:#10b981,color:#fff,stroke:#065f46
    style N fill:#7f1d1d,color:#fff,stroke:#450a0a

```

---

## 7. Workflow & Orchestration

The system operates as a continuous stream-processing pipeline orchestrated as follows:

1. **Frame Capture and Skip:** The OpenCV-based `pipeline.detect` camera manager pulls live RTSP or file-based video frames. It forwards every 3rd frame to the model while holding track centroids in buffer.
2. **Inference & Spatial Mapping:** YOLOv8s extracts bounding boxes, which are passed to ByteTrack to preserve identity. Centroids are passed through Shapely polygons from `data/store_layout.json` to assign coordinates to active zones.
3. **Hybrid Staff Filtering & Re-ID:** Bounding boxes are scored by both HSV chi² (staff detection) and LAB cosine similarity (visitor Re-ID). A weighted confidence merge (`0.65 × LAB + 0.35 × HSV_inv`) produces a single ReIDResult per track.
4. **Buffered Batch Emission with Bus Fallback:** Events are buffered and pushed in batches of up to 500. Kafka is tried first (3 attempts, exponential backoff), with Redis Streams as fallback. Idempotency is enforced via `event_id` pre-query before any write.
5. **Database Transaction Ingestion:** FastAPI handles the batch inside an isolated PostgreSQL transaction. Novel events are written; duplicates are counted and returned in the response.
6. **State-Machine Updates:** Verified events are fed into the SQLAlchemy Session State Machine, updating customer tracks, flags, and aggregate metrics.
7. **Background Alert Scan:** An asynchronous loop (`asyncio.create_task`) runs every 30 seconds, evaluating KPIs and upserting store alert rows.
8. **UI Rendering:** The Rich TUI Dashboard subscribes via WebSocket (falls back to HTTP polling every 2s when `DASHBOARD_MODE=TUI`), rendering KPI tiles, conversion funnel, zone heatmap, and severity-coded anomaly log.

---

## 8. Data Flow & State Management

The session state machine maintains the operational state of the store. When raw event sequences are ingested, they are processed step-by-step to transition database rows:

```
                  ┌───────────────────────┐
                  │      No Session       │
                  └──────────┬────────────┘
                             │
                             │ ENTRY Event
                             ▼
                  ┌───────────────────────┐
                  │     Session Open      │
                  │   converted = False   │
                  └──────────┬────────────┘
                             │
            ┌────────────────┴────────────────┐
            │ ZONE_ENTER                      │ BILLING_QUEUE_JOIN
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│     Browsing Zone     │         │    In Checkout Line   │
│ update total_dwell_ms │         │ set billing_join_time │
└──────────┬────────────┘         └──────────┬────────────┘
           │                                 │
           │ EXIT                            ├────────────────────────┐
           ▼                                 │ POS Ingest             │ BILLING_QUEUE_ABANDON
┌───────────────────────┐                    │ (Within 5 Min Window)  │
│    Session Closed     │                    ▼                        ▼
│   (Finalize Dwell)    │         ┌───────────────────────┐  ┌───────────────────────┐
└───────────────────────┘         │   Session Converted   │  │    Queue Abandoned    │
                                  │   converted = True    │  │ queue_abandoned = True│
                                  └──────────┬────────────┘  └───────────────────────┘
                                             │
                                             │ EXIT
                                             ▼
                                  ┌───────────────────────┐
                                  │   Converted Closed    │
                                  └───────────────────────┘
```

---

## 9. Tech Stack

| Technology Layer | Component | Purpose |
|---|---|---|
| **Programming Language** | Python 3.11+ | Core language for edge CV, API server, and terminal UI. |
| **Computer Vision** | OpenCV | Efficient video frame capture and camera rendering. |
| **Object Detection** | Ultralytics YOLOv8s | Balance of person-detection accuracy ($\sim48\text{ mAP}$) and edge-device inference speed. |
| **Object Tracking** | ByteTrack | Multi-object association using second-pass tracking for occluded retail environments. |
| **Spatial Calculations** | Shapely | Fast vector polygon intersection checks for store zone boundaries. |
| **API Framework** | FastAPI | High-performance asynchronous REST API supporting non-blocking backend operations. |
| **Message Bus (Primary)** | Kafka + aiokafka | Async event streaming with exponential-backoff retry and idempotent ingestion. |
| **Message Bus (Fallback)** | Redis Streams + aioredis | Async fallback bus via XADD pipeline when Kafka broker is unavailable. |
| **Logging Engine** | Structlog | JSON-structured logs with injected request IDs for production debugging. |
| **Database ORM** | SQLAlchemy 2.0 (Async) | Modern asynchronous object-relational mapper for scalable database interactions. |
| **Production Database** | PostgreSQL (Render) | Managed relational storage with indexing for high-concurrency event writes. |
| **Local / Test Database** | SQLite (`aiosqlite`) | Light async database fallback for zero-install local testing and dev. |
| **Visual Dashboard UI** | Rich + WebSocket | Terminal dashboard with KPI tiles, funnel bars, heatmap, and anomaly log. |
| **Orchestration** | Docker & Docker Compose | Containerization of PostgreSQL, API service, CV pipeline, and dashboard UI. |
| **Cloud Deployment** | Render | Multi-stage Docker build, managed PostgreSQL, auto-deploy from GitHub. |
| **Unit / Integration Tests** | Pytest & Pytest-Cov | Validation suite covering data pipelines, API routes, and edge-cases. |

---

## 10. AI Deep Dive — Gemini 2.5 Flash

Building a production-ready system requires balancing automated AI suggestions with real-world software engineering practices. Below is a breakdown of how AI assisted our design decisions, where we aligned, and where human engineering chose to override:

> [!NOTE]
> **Decision 1: Event Schema Modeling**
> * **AI Suggestion:** Recommended a flat database model or separate Pydantic models for each event type (ENTRY, DWELL, EXIT) to maximize type safety.
> * **Our Decision:** Chose a nested `metadata` model to ensure complete compliance with the evaluation harness while enforcing strict `0 ≤ confidence ≤ 1` ranges. We kept the schema unified to allow for easier ingestion of large event streams.

> [!TIP]
> **Decision 2: Anomaly Detection Architecture**
> * **AI Suggestion:** Initially proposed running retail anomaly calculations (e.g., dead-zone or queue spikes) synchronously inside GET requests to the `/anomalies` endpoint.
> * **Our Decision:** Overrode this approach because computing live metrics across thousands of sessions on every request adds severe latency. We moved the detector to a background `asyncio.Task` running every 30 seconds. The `/anomalies` endpoint now performs an $O(1)$ read from pre-computed tables.

> [!WARNING]
> **Decision 3: Message Bus Resilience**
> * **AI Suggestion:** Recommended pure Kafka from day one for all event ingestion.
> * **Our Decision:** Accepted Kafka as primary but added an automatic Redis Streams fallback using `aioredis` with exponential-backoff retry (3 attempts, 0.5→1.0→2.0s). This ensures zero event loss during transient broker outages without requiring operator intervention.

---

## 11. Impact

By deploying the Store Intelligence System, retail operators gain immediate access to actionable operational insights:

* **True Store Conversion Rates:** By filtering out employees and deduplicating customer re-entries, the dashboard displays the exact percentage of unique visitors who made a purchase.
* **Frictionless Funnel Analysis:** Pinpoints the exact stages where shoppers drop off (e.g., browsing but not queueing, or queueing and then abandoning due to wait times).
* **Operational Agility:** Real-time alerts for queue spikes allow managers to dynamically open checkout counters before customers walk out, protecting margins.
* **Layout Optimization:** High-fidelity heatmaps show which store zones are highly engaging and which are "dead zones," enabling data-driven product placement.

---

## 12. Real-World Use Cases

### 🏪 Case 1: Resolving Checkout Friction
A cosmetic store experiences a sudden drop in sales conversion. The live terminal alert ticker triggers a `BILLING_QUEUE_SPIKE` warning. Historical analytics show that whenever the checkout queue exceeds 5 people, abandonment rates climb by $40\%$. The store manager receives the alert and immediately opens a second register, resolving the bottleneck.

### 🧪 Case 2: A/B Testing Store Aisles
The marketing team moves a premium perfume display to the back-left corner of the store. Using the dynamic `/heatmap` endpoint, they notice the zone's frequency score remains below 10 (a designated `DEAD_ZONE`). The team uses the data to move the display to a higher-traffic zone, increasing interaction scores from 10 to 85.

### 🛡️ Case 3: Keeping Analytics Pure
A retail fashion boutique has five staff members restocking shelves throughout the day. Under standard footfall systems, their continuous movements inflate daily visitor numbers, artificially dragging down the conversion rate. The system's HSV clothing filter and path heuristics classify these movements as staff, preserving the integrity of the store's conversion analytics.

---

## 13. Comparison

| Metric / Feature | IR Beam Entry Counters | High-End Cloud VLM Streaming | Store Intelligence System (Ours) |
|---|---|---|---|
| **Identity Deduplication** | ❌ None | ✅ High (Deep Learning OSNet) | ✅ High (Hybrid HSV + LAB) |
| **Store Zone Telemetry** | ❌ None | ✅ Full Zone Tracking | ✅ Full Zone Tracking |
| **Compute / Bandwidth Cost** | 🟢 Extremely Low | 🔴 Extremely High ($100\text{s}$ per camera/mo) | 🟢 Low (Edge CPU/GPU) |
| **Privacy Compliance** | 🟢 High (No cameras) | 🔴 Low (Raw video to cloud) | 🟢 High (Local processing, no PII stored) |
| **Message Bus Resilience** | 🔴 None | 🟡 Cloud-managed | 🟢 Kafka + Redis fallback |
| **Setup Time** | 🟢 Quick | 🔴 Long (training + cloud setup) | 🟢 Quick (5-Command Setup) |
| **Operational Costs** | 🟢 Low | 🔴 High VLM API Costs | 🟢 Low (Render free tier + self-hosted edge) |

---

## 14. Scalability

Our architecture is designed to scale to 40+ concurrent retail stores:

* **Non-blocking Event Loops:** FastAPI's async route handlers process bulk writes without blocking, ensuring the server can handle high concurrent traffic.
* **Optimized Bulk Ingest:** The `/events/ingest` handler batches up to 500 events, performing single-query deduplication lookups to prevent database locks.
* **Database Indexing:** Composite indices on `(store_id, entry_time)` ensure fast query execution for metrics endpoints, even with millions of rows.
* **Bus Failover:** Kafka → Redis Streams fallback ensures ingestion continues during transient broker failures with zero manual intervention.
* **Scalable Funnel Queries:** While the current system processes visitor counts in memory, it is designed to transition to native PostgreSQL `COUNT(DISTINCT visitor_id)` queries as database sizes grow.

---

## 15. Responsible AI and Ethics

We treat privacy as a core engineering requirement:

* **Privacy by Design:** The system does not use facial recognition or biometric scanning.
* **Anonymized Data Representation:** Raw camera frames are processed locally at the edge and immediately discarded. Bounding boxes are converted into anonymous coordinate logs and a 96-dimensional LAB color histogram. No personal identifiable information (PII) is ever written to the database.
* **Memory-Resident Identity TTL:** The Re-ID appearance gallery is stored strictly in-memory at the edge and is automatically purged after 5 minutes, ensuring visitor data is ephemeral.

---

## 16. Evaluation Criteria Alignment

| Evaluation Criterion | Implementation Details | Evidence in Codebase |
|---|---|---|
<<<<<<< HEAD
| **Functional Completeness** | End-to-end flow from raw video to live terminal dashboard is fully operational and deployed. | [detect.py](pipeline/detect.py), [main.py](app/main.py), [terminal_dashboard.py](dashboard/terminal_dashboard.py) |
=======
| **Functional Completeness** | End-to-end flow from raw video to live terminal dashboard is fully operational and deployed. Validated against both Store 1 and Store 2 footage. | [detect.py](pipeline/detect.py), [main.py](app/main.py), [terminal_dashboard.py](dashboard/terminal_dashboard.py) |
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
| **Code Coverage** | Comprehensive automated test suite ensuring correct metric calculations, funnel operations, and health checks. | Enforced at $>70\%$ in [pytest.ini](pytest.ini) |
| **Edge-Case Resilience** | System handles empty stores, zero transactions, employee filtering, Kafka outages, and re-entry tracking without breaking. | [test_ingestion.py](tests/test_ingestion.py), [test_metrics.py](tests/test_metrics.py) |
| **Production Readiness** | Structured logging with trace IDs, graceful error handling, multi-stage Docker build, deployed on Render with managed PostgreSQL. | [logging_config.py](app/logging_config.py), [Dockerfile.api](Dockerfile.api), [railway.toml](railway.toml) |

---

## 17. Trade-offs

* **Model Accuracy vs. Compute Cost:** We chose **YOLOv8s** over YOLOv8m or RT-DETR. While the larger models offer a minor accuracy bump, they double hardware requirements. YOLOv8s delivers strong person detection at a fraction of the compute cost.
* **Re-ID Method:** We opted for a **Hybrid HSV + LAB approach** over a deep OSNet feature extractor. Deep extractors are highly robust but require dedicated GPUs. The hybrid approach runs in $<1\text{ms}$ on low-cost CPUs, handles retail lighting changes well, and doubles as a staff filter.
* **ORM Usage:** We chose **SQLAlchemy ORM** over raw SQL queries. While raw SQL has slightly less overhead, the ORM provides strong type safety and allows us to seamlessly swap between PostgreSQL and SQLite.
* **Message Bus:** We chose **Kafka + Redis fallback** over a single-bus approach. The added complexity of two clients is offset by zero-downtime resilience during transient broker failures.

---

## 18. Project Complexity Tiers

```
┌────────────────────────────────────────────────────────┐
│ TIER 3: ADVANCED                                       │
│ • Hybrid HSV + LAB Re-ID with Weighted Confidence Merge│
│ • Kafka + Redis Streams Fallback with Backoff Retry    │
│ • Background asyncio Anomaly Alerts Daemon             │
│ • Multi-Stage Docker Build — Render Cloud Deployment   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ TIER 2: INTERMEDIATE                                   │
│ • Asynchronous Database Connection Pools (SQLAlchemy)  │
│ • Pydantic Schema Validation & Custom Validators       │
│ • WebSocket Dashboard Feed + HTTP-Poll Fallback        │
│ • Multi-Container Docker Orchestration (Compose)       │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ TIER 1: FOUNDATIONAL                                   │
│ • Structured Logging Config (structlog)                │
│ • Unit Testing Framework (pytest)                      │
│ • REST API Route Design (FastAPI)                      │
└────────────────────────────────────────────────────────┘
```

---

## 19. Installation & Setup

### **Quick Setup (Docker Recommended)**

Full system — PostgreSQL + API + detection pipeline + live dashboard — in **5 commands**:

```bash
# 1. Clone the repository
git clone https://github.com/riddhisharma-sudo/purplle-Store-intelligence.git
cd purplle-Store-intelligence

# 2. Copy environment config
cp .env.example .env

# 3. Start all services (DB + API + event simulator + dashboard)
docker compose up --build
```

The simulator starts immediately and populates the API with realistic visitor events for `STORE_BLR_002` (Brigade Road, Bangalore).

```bash
# 4. (Optional) Run the YOLOv8 detection pipeline on the real CCTV clips
#    See section 4a below for full instructions.

# 5. Attach to the live terminal dashboard
docker compose attach dashboard
```

> **Note on CCTV clips:** Clips for Store 1 and Store 2 are not included in the repository — provided separately by the challenge organizers (licence: challenge use only, must not be redistributed). Place Store 1 clips in a `Store 1/` directory and Store 2 clips in a `Store 2/` directory. Without the clips, `docker compose up` still works fully via the built-in event simulator.

**Verify the API is live:**
```bash
# Local
curl http://localhost:8000/health
<<<<<<< HEAD
curl "http://localhost:8000/stores/STORE_BLR_002/metrics"

# Live Render deployment
curl https://purplle-store-intelligence-17fl.onrender.com/health
curl "https://purplle-store-intelligence-17fl.onrender.com/stores/STORE_BLR_002/metrics"
=======
curl "http://localhost:8000/stores/STORE_PRP_001/metrics?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_002/metrics?date=2026-06-01"

# Live Render deployment
curl https://purplle-store-intelligence-17fl.onrender.com/health
curl "https://purplle-store-intelligence-17fl.onrender.com/stores/STORE_PRP_001/metrics?date=2026-04-10"
curl "https://purplle-store-intelligence-17fl.onrender.com/stores/STORE_002/metrics?date=2026-06-01"
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
```

---

### **Manual Local Installation (For Development & Testing)**

#### **1. Set up your Python environment**
Ensure you are using Python 3.11+:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

#### **2. Install required packages**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-pipeline.txt
```

#### **3. Start the local server**
```bash
python -m uvicorn app.main:app --reload --port 8000
```

#### **4a. Run the detection pipeline on the real CCTV footage**

Clips are mapped to camera roles via `data/clips_config.json`. The system supports two stores:

**Store 1 — `STORE_PRP_001`** (Skincare & Makeup, recorded 10 April 2026)

| File | Camera Role | Zone |
|---|---|---|
| `CAM 3 - entry.mp4` | `CAM_ENTRY_01` | Entry/Exit glass door threshold |
| `CAM 1 - zone.mp4` | `CAM_FLOOR_01` | Skincare wall — Farmstay, TFS, Good Vibes, Minimalist, DERMDOC |
| `CAM 2 - zone.mp4` | `CAM_FLOOR_02` | Makeup wall — Alps, L'Oreal, Lakme, FacesCanada, Maybelline |
| `CAM 5 - billing.mp4` | `CAM_BILLING_01` | Billing counter / POS terminal |

**Store 2 — `STORE_002`** (Multi-zone layout, recorded 1 June 2026)

| File | Camera Role | Zone |
|---|---|---|
| `entry 1.mp4` | `CAM_ENTRY_01` | Left entry glass panel |
| `entry 2.mp4` | `CAM_ENTRY_02` | Right entry glass panel |
| `zone.mp4` | `CAM_FLOOR_01` | Main floor — Gondola displays + Makeup trial stations |
| `billing_area.mp4` | `CAM_BILLING_01` | Cash counter / billing area |

```bash
pip install -r requirements-pipeline.txt

<<<<<<< HEAD
=======
# Run Store 1
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
python -m pipeline.detect \
  --clips-config data/clips_config.json \
  --clips-dir "Store 1" \
  --layout data/store_layout.json \
  --api-url http://localhost:8000 \
  --output events_store1.jsonl \
  --conf 0.35

<<<<<<< HEAD
=======
# Run Store 2
python -m pipeline.detect \
  --clips-config data/clips_config.json \
  --clips-dir "Store 2" \
  --layout data/store_layout.json \
  --api-url http://localhost:8000 \
  --output events_store2.jsonl \
  --conf 0.35

# Load POS transactions — supports Purplle POS CSV format.
# ST1008 is automatically remapped to STORE_BLR_002.
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
python -m pipeline.load_pos \
  --csv "POS - sample transactions.csv" \
  --api-url http://localhost:8000
```

#### **4b. Run the customer event simulator** *(no clips needed)*
```bash
# Against local server
python -m pipeline.simulate --store-id STORE_BLR_002 --layout data/store_layout.json --api-url http://localhost:8000 --visitors 100 --speed 30

<<<<<<< HEAD
#### **4b. Run the customer event simulator** *(no clips needed)*
```bash
# Against local server
python -m pipeline.simulate --store-id STORE_BLR_002 --layout data/store_layout.json --api-url http://localhost:8000 --visitors 100 --speed 30

=======
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
# Against live Render deployment
python -m pipeline.simulate --store-id STORE_BLR_002 --api-url https://purplle-store-intelligence-17fl.onrender.com --visitors 50 --speed 10
```

#### **5. Launch the Terminal TUI Dashboard**
```bash
<<<<<<< HEAD
# Against local server
python -m dashboard.terminal_dashboard --store-id STORE_BLR_002 --api-url http://localhost:8000

# Against live Render deployment
python -m dashboard.terminal_dashboard --store-id STORE_BLR_002 --api-url https://purplle-store-intelligence-17fl.onrender.com

# Force HTTP-polling fallback (no WebSocket)
DASHBOARD_MODE=TUI python -m dashboard.terminal_dashboard --store-id STORE_BLR_002 --api-url https://purplle-store-intelligence-17fl.onrender.com
=======
# Store 1
python -m dashboard.terminal_dashboard --store-id STORE_PRP_001 --api-url http://localhost:8000

# Store 2
python -m dashboard.terminal_dashboard --store-id STORE_002 --api-url http://localhost:8000

# Against live Render deployment
python -m dashboard.terminal_dashboard --store-id STORE_PRP_001 --api-url https://purplle-store-intelligence-17fl.onrender.com
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
```

#### **6. Run the test suite**
```bash
pytest -v --cov=app --cov=pipeline
```

---

## 20. Why This Will Win

The Store Intelligence System is built to win hackathons and enterprise evaluations alike:

1. **Production-Ready and Deployed:** Live on Render with managed PostgreSQL, multi-stage Docker build, structured logs, and automated health checks — not just a local demo.
2. **Resource-Efficient Architecture:** Intelligent frame-skipping and CPU-optimized Hybrid Re-ID allow the platform to run on standard, low-cost hardware.
3. **Resilient by Design:** Kafka + Redis Streams fallback with exponential-backoff retry ensures zero event loss during broker outages without manual intervention.
4. **Visually Stunning Terminal UI:** The interactive terminal dashboard immediately captures attention, making metrics clear and accessible without a browser.
5. **Actionable Retail Insights:** Built around key business objectives (conversion rates, funnel leakage, queue management) to deliver clear operational value.

---

## 21. Future Scope

* **Upgrade to YOLOv10 / RT-DETR:** Incorporating the latest object-detection architectures to further reduce latency and improve edge performance.
* **Database-Side Aggregations:** Shifting funnel calculations from memory-based Python logic to optimized SQL subqueries for multi-store scale.
* **Live Camera Feeds:** Adding native support for RTSP video streams to process live retail security cameras in real-time.
* **Grafana Dashboard:** Exposing PostgreSQL metrics to a hosted Grafana instance for richer time-series visualizations alongside the TUI.

---

## 22. FAQ

#### **Q: How does the system handle tracking when customers are blocked by shelves?**
**A:** We use ByteTrack's dual-pass matching system. Even if a customer is temporarily occluded, their track is kept active at a lower confidence threshold rather than being immediately discarded.

#### **Q: Can I run this system without a GPU?**
**A:** Yes! Thanks to our adaptive frame-skipping ($5\text{fps}$ effective) and lightweight Hybrid HSV + LAB Re-ID algorithm, the entire pipeline runs smoothly on standard multi-core CPUs.

#### **Q: Are customer face images stored in the database?**
**A:** No. The visual pipeline processes frames locally at the edge. Only anonymous spatial coordinates and color histograms are extracted, keeping customer identities private.

#### **Q: What happens if the Kafka broker goes down?**
**A:** The ingestion engine automatically falls back to Redis Streams via `aioredis` after 3 exponential-backoff retry attempts. The response includes a `bus` field indicating which transport was used (`"kafka"` or `"redis"`).

---

## 23. Lessons Learned

1. **Lightweight CV Algorithms Win on the Edge:** While heavy deep-learning Re-ID models are highly accurate, a hybrid HSV + LAB approach delivers $90\%$ of the performance at $1\%$ of the compute cost — and doubles as a staff classifier.
2. **Design for Bus Failure from Day One:** Adding a Redis Streams fallback after the fact is painful. Building the retry + fallback loop into the initial ingestion handler costs one afternoon and saves hours of production incidents.
3. **Structured Logging is Essential:** In complex, multi-service systems (CV nodes, API gateways, message buses, database transactions), structured JSON logs with trace IDs save hours of debugging time.

---

<p align="center">
   For the <strong>Purplle Tech Challenge 2026</strong>.<br/>
  <a href="https://purplle-store-intelligence-17fl.onrender.com/docs">Live API Docs</a> ·
  <a href="https://github.com/riddhisharma-sudo/purplle-Store-intelligence">GitHub Repo</a>
<<<<<<< HEAD
</p>

=======
</p>
>>>>>>> 4934f2c (Final Purplle Round 2 submission)
