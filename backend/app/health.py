from .protocol import timestamp


async def readiness(runtime):
    redis_ready = await runtime.broker.ping()
    ready = not runtime.sessions.draining and redis_ready
    database = "disabled"
    if runtime.accounts.storage:
        try:
            await runtime.accounts.call("check")
            database = "connected"
        except Exception:
            database = "unavailable"
            ready = False
    return {
        "status": "healthy" if ready else "degraded",
        "container_id": runtime.replica,
        "timestamp": timestamp(),
        "release_id": runtime.settings.release_id,
        "subsystems": {
            "database": database,
            "redis_connection": "connected" if redis_ready else "unavailable",
            "subscriber_heartbeat": "fresh" if runtime.broker.ready else "stale",
            "generation_nonce": runtime.broker.generation,
            "active_connections": runtime.sessions.reserved,
            "capacity_available": max(0, runtime.settings.max_connections_per_replica
                                      - runtime.sessions.reserved),
        },
    }, 200 if ready else 503
