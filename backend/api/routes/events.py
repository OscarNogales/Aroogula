import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from backend.app.event_bus import event_bus

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def stream_events(request: Request):
    async def event_generator():
        async for event in event_bus.subscribe():
            if await request.is_disconnected():
                break

            yield (
                f"event: {event['type']}\n"
                f"data: {json.dumps(event)}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )

@router.get("/live")
def get_live_events(limit: int = Query(default=50, ge=1, le=200)):
    raw_events = event_bus.get_recent(limit)

    events = []

    for i, event in enumerate(reversed(raw_events)):
        payload = event.get("payload", {})
        event_type = event.get("type", "LOG")

        events.append({
            "id": f"EVT-{i}",
            "type": payload.get("side") or event_type,
            "ticker": payload.get("ticker", "--"),
            "title": (
                payload.get("title")
                or payload.get("message")
                or event_type
            ),
            "summary": (
                payload.get("summary")
                or payload.get("reason")
                or payload.get("reasoning")
                or payload.get("message")
                or ""
            ),
            "time": event.get("timestamp", "now"),
        })

    return {
        "status": "success",
        "message": f"Retrieved {len(events)} recent events.",
        "data": {
            "events": events,
        },
    }