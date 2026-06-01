"""
dashboard/terminal_dashboard.py
────────────────────────────────
Rich-based terminal dashboard with:
  • WebSocket primary mode (live push from FastAPI)
  • HTTP polling fallback when env DASHBOARD_MODE=TUI or WebSocket fails
  • Live panels: visitors, conversion rate, queue depth, zone heatmap
  • Anomaly log panel with colour-coded severity
  • Conversion funnel chart (Sparklines via Rich bar chart)

Run
───
    python -m dashboard.terminal_dashboard \
        --store-id STORE_BLR_002 \
        --api-url  http://localhost:8000

Force TUI/polling fallback:
    DASHBOARD_MODE=TUI python -m dashboard.terminal_dashboard ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

# ── Rich imports ───────────────────────────────────────────────────────────────
from rich import box
from rich.align import Align
from rich.bar import Bar
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

POLL_INTERVAL_SEC = 2          # HTTP polling cadence
FUNNEL_MAX_COLS   = 40         # width of funnel bar chart

# Severity → Rich colour
SEVERITY_COLOUR = {
    "CRITICAL": "bold red",
    "WARN":     "yellow",
    "INFO":     "cyan",
    "OK":       "green",
}


# ══════════════════════════════════════════════════════════════════════════════
# Data model (populated from API responses)
# ══════════════════════════════════════════════════════════════════════════════

class DashboardState:
    def __init__(self) -> None:
        self.store_id:        str  = "—"
        self.active_visitors: int  = 0
        self.conversion_rate: float = 0.0
        self.queue_depth:     int  = 0
        self.total_sessions:  int  = 0
        self.converted:       int  = 0
        self.abandoned:       int  = 0
        self.zone_heatmap:    Dict[str, int] = {}
        self.anomalies:       list = []
        self.last_updated:    str  = "—"
        self.data_source:     str  = "—"

    def ingest(self, data: Dict[str, Any], source: str = "http") -> None:
        self.store_id        = data.get("store_id", self.store_id)
        self.active_visitors = data.get("active_visitors", self.active_visitors)
        self.conversion_rate = data.get("conversion_rate", self.conversion_rate) or 0.0
        self.queue_depth     = data.get("queue_depth", self.queue_depth)
        self.total_sessions  = data.get("total_sessions", self.total_sessions)
        self.converted       = data.get("converted_sessions", self.converted)
        self.abandoned       = data.get("abandoned_sessions", self.abandoned)
        self.zone_heatmap    = data.get("zone_heatmap", self.zone_heatmap) or {}
        self.anomalies       = data.get("anomalies", self.anomalies) or []
        self.last_updated    = datetime.now().strftime("%H:%M:%S")
        self.data_source     = source


STATE = DashboardState()


# ══════════════════════════════════════════════════════════════════════════════
# Layout builders
# ══════════════════════════════════════════════════════════════════════════════

def _kpi_panel() -> Panel:
    """Top row: four KPI tiles."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="center", ratio=1)

    def _kpi(label: str, value: str, colour: str) -> Text:
        t = Text(justify="center")
        t.append(f"{value}\n", style=f"bold {colour}")
        t.append(label, style="dim")
        return t

    # Queue depth colour coding
    q_colour = "green"
    if STATE.queue_depth >= 10:
        q_colour = "bold red"
    elif STATE.queue_depth >= 5:
        q_colour = "yellow"

    grid.add_row(
        _kpi("Active Visitors",    str(STATE.active_visitors), "bold cyan"),
        _kpi("Conversion Rate",    f"{STATE.conversion_rate * 100:.1f}%", "bold green"),
        _kpi("Queue Depth",        str(STATE.queue_depth),     q_colour),
        _kpi("Total Sessions",     str(STATE.total_sessions),  "white"),
    )
    return Panel(grid, title="[bold]Store KPIs[/bold]", box=box.ROUNDED, padding=(1, 2))


def _funnel_panel() -> Panel:
    """Conversion funnel: sessions → converted vs abandoned."""
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True)
    table.add_column("Stage",       style="bold", width=18)
    table.add_column("Count",       justify="right", width=8)
    table.add_column("",            ratio=1)   # bar

    total = max(STATE.total_sessions, 1)
    rows = [
        ("Entered Store",  STATE.total_sessions, "steel_blue1"),
        ("Converted",      STATE.converted,      "green"),
        ("Queue Abandoned", STATE.abandoned,      "yellow"),
    ]
    for label, count, colour in rows:
        ratio  = count / total
        filled = int(ratio * FUNNEL_MAX_COLS)
        bar    = f"[{colour}]{'█' * filled}{'░' * (FUNNEL_MAX_COLS - filled)}[/{colour}]"
        table.add_row(label, str(count), bar)

    return Panel(table, title="[bold]Conversion Funnel[/bold]", box=box.ROUNDED)


def _heatmap_panel() -> Panel:
    """Zone heatmap as a sorted bar chart."""
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True)
    table.add_column("Zone",    style="bold", width=20)
    table.add_column("Events",  justify="right", width=8)
    table.add_column("",        ratio=1)

    items = sorted(STATE.zone_heatmap.items(), key=lambda x: x[1], reverse=True)
    if not items:
        table.add_row("[dim]No zone data[/dim]", "", "")
    else:
        max_val = max(v for _, v in items) or 1
        for zone, count in items:
            ratio  = count / max_val
            filled = int(ratio * FUNNEL_MAX_COLS)
            colour = "magenta" if zone in {"BILLING_QUEUE", "ENTRY"} else "blue"
            bar    = f"[{colour}]{'█' * filled}{'░' * (FUNNEL_MAX_COLS - filled)}[/{colour}]"
            table.add_row(zone, str(count), bar)

    return Panel(table, title="[bold]Zone Heatmap[/bold]", box=box.ROUNDED)


def _anomaly_panel() -> Panel:
    """Anomaly log panel — most recent 8 alerts, colour by severity."""
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True)
    table.add_column("Time",    width=10)
    table.add_column("Sev",     width=10)
    table.add_column("Type",    width=26)
    table.add_column("Action",  ratio=1)

    recent = STATE.anomalies[:8]
    if not recent:
        table.add_row("[dim]No anomalies[/dim]", "", "", "")
    else:
        for a in recent:
            sev     = a.get("severity", "INFO")
            colour  = SEVERITY_COLOUR.get(sev, "white")
            ts      = a.get("triggered_at", "")[:19].replace("T", " ")[-8:]
            table.add_row(
                ts,
                f"[{colour}]{sev}[/{colour}]",
                a.get("alert_type", "—"),
                a.get("suggested_action", "—"),
            )

    return Panel(table, title="[bold]Anomaly Log[/bold]", box=box.ROUNDED)


def _status_bar() -> Text:
    t = Text()
    t.append(f" Store: {STATE.store_id} ", style="bold white on dark_blue")
    t.append(f" Source: {STATE.data_source} ", style="bold white on dark_green")
    t.append(f" Updated: {STATE.last_updated} ", style="dim")
    return t


def _build_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="status",  size=1),
        Layout(name="kpis",    size=7),
        Layout(name="middle",  ratio=1),
        Layout(name="anomaly", size=12),
    )
    layout["middle"].split_row(
        Layout(name="funnel",  ratio=1),
        Layout(name="heatmap", ratio=1),
    )
    return layout


def _refresh_layout(layout: Layout) -> None:
    layout["status"].update(_status_bar())
    layout["kpis"].update(_kpi_panel())
    layout["funnel"].update(_funnel_panel())
    layout["heatmap"].update(_heatmap_panel())
    layout["anomaly"].update(_anomaly_panel())


# ══════════════════════════════════════════════════════════════════════════════
# Data fetchers
# ══════════════════════════════════════════════════════════════════════════════

async def _http_poll(api_url: str, store_id: str) -> None:
    """HTTP polling loop (fallback / TUI mode)."""
    metrics_url   = f"{api_url}/stores/{store_id}/metrics"
    anomalies_url = f"{api_url}/stores/{store_id}/anomalies"

    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                m_resp = await client.get(metrics_url)
                a_resp = await client.get(anomalies_url)
                data = m_resp.json() if m_resp.status_code == 200 else {}
                data["anomalies"] = (
                    a_resp.json().get("anomalies", [])
                    if a_resp.status_code == 200 else []
                )
                STATE.ingest(data, source="http-poll")
            except Exception as exc:
                logger.warning("HTTP poll error: %s", exc)
                STATE.data_source = "http-poll (error)"
            await asyncio.sleep(POLL_INTERVAL_SEC)


async def _ws_subscribe(api_url: str, store_id: str) -> None:
    """WebSocket subscription loop (primary mode)."""
    ws_url = api_url.replace("http", "ws", 1) + f"/ws/{store_id}"
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20) as ws:
                logger.info("WebSocket connected: %s", ws_url)
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        STATE.ingest(data, source="websocket")
                    except json.JSONDecodeError:
                        pass
        except Exception as exc:
            logger.warning("WebSocket error (%s) — reconnecting in 3s", exc)
            STATE.data_source = "ws (reconnecting)"
            await asyncio.sleep(3)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

async def _run(api_url: str, store_id: str) -> None:
    STATE.store_id = store_id

    # Determine mode: env override or WS unavailable → TUI/polling fallback
    force_tui = os.getenv("DASHBOARD_MODE", "").upper() == "TUI"
    use_ws    = WS_AVAILABLE and not force_tui

    console = Console()
    layout  = _build_layout()

    # Launch data-fetch task
    if use_ws:
        fetch_task = asyncio.create_task(_ws_subscribe(api_url, store_id))
    else:
        logger.warning("TUI/polling mode active (DASHBOARD_MODE=TUI or websockets missing).")
        fetch_task = asyncio.create_task(_http_poll(api_url, store_id))

    with Live(layout, console=console, refresh_per_second=2, screen=True):
        try:
            while True:
                _refresh_layout(layout)
                await asyncio.sleep(0.5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            fetch_task.cancel()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Purplle Store Intelligence — Live Dashboard")
    p.add_argument("--store-id", default="STORE_BLR_002")
    p.add_argument("--api-url",  default="http://localhost:8000")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    def _handle_sigint(sig, frame):  # noqa: ANN001
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)
    asyncio.run(_run(args.api_url, args.store_id))


if __name__ == "__main__":
    main()
