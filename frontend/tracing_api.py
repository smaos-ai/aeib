"""
FastAPI trace endpoints for real-time distributed tracing.
"""

import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from tracing_models import collector

router = APIRouter(prefix="/api/traces", tags=["tracing"])


@router.get("/")
async def list_traces(limit: int = 20):
    """List recent traces."""
    return collector.get_recent_traces(limit)


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """Get full trace with all spans."""
    trace = collector.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/{trace_id}/stream")
async def stream_trace(trace_id: str):
    """SSE stream for real-time trace updates."""

    async def event_generator():
        queue = asyncio.Queue()
        events_sent = 0

        def on_event(event):
            if event["trace_id"] == trace_id:
                queue.put_nowait(event)

        collector.subscribe(on_event)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    events_sent += 1
                    if events_sent > 100:  # Safety limit
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        finally:
            collector.unsubscribe(on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
