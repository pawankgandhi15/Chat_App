import json
import logging

from prometheus_client import CollectorRegistry, Counter, Gauge


def log_event(event: str, **fields):
    # Callers pass bounded outcome classes, never exception messages or request data.
    logging.getLogger("chat").info(json.dumps({"event": event, **fields}))


class Metrics:
    def __init__(self, replica: str):
        self.registry = CollectorRegistry()
        self.connections = Gauge("chat_connections_active", "Active admitted sockets",
                                 registry=self.registry)
        self.queued = Gauge("chat_outbound_queue_bytes", "Queued serialized bytes",
                            registry=self.registry)
        self.ready = Gauge("chat_subscriber_ready", "Fresh current-generation subscriber",
                           registry=self.registry)
        self.published = Counter("chat_messages_published_total", "Publication outcomes",
                                 ["status"], registry=self.registry)
        self.deliveries = Counter("chat_deliveries_total", "Socket delivery outcomes",
                                  ["status"], registry=self.registry)
        self.admission = Counter("chat_admission_total", "Admission outcomes",
                                 ["status"], registry=self.registry)
