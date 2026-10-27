from .protocol import timestamp


async def readiness(runtime):
    ready = not runtime.sessions.draining and await runtime.broker.ping()
    return {
        "status": "healthy" if ready else "degraded",
        "container_id": runtime.replica,
        "timestamp": timestamp(),
        "release_id": runtime.settings.release_id,
        "subsystems": {
            "redis_connection": "connected" if ready else "unavailable",
            "subscriber_heartbeat": "fresh" if runtime.broker.ready else "stale",
            "generation_nonce": runtime.broker.generation,
            "active_connections": runtime.sessions.reserved,
            "capacity_available": max(0, runtime.settings.max_connections_per_replica
                                      - runtime.sessions.reserved),
        },
    }, 200 if ready else 503
