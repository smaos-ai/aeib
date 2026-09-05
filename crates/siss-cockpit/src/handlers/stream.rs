use crate::state::CockpitState;
use axum::extract::State;
use axum::response::sse::{Event, KeepAlive, Sse};

pub async fn stream_agent_events(
    State(state): State<CockpitState>,
) -> Sse<impl futures::stream::Stream<Item = Result<Event, std::convert::Infallible>>> {
    let mut rx = state.subscribe();

    let stream = async_stream::stream! {
        // Send buffered events first (replay buffer)
        for event in state.buffered_events() {
            if let Ok(json) = serde_json::to_string(&event) {
                yield Ok(Event::default().data(json));
            }
        }

        // Then stream live events
        loop {
            match rx.recv().await {
                Ok(event) => {
                    if let Ok(json) = serde_json::to_string(&event) {
                        yield Ok(Event::default().data(json));
                    }
                }
                Err(_) => break,
            }
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}
