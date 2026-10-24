"""OpenTelemetry to Azure Application Insights (only when a connection string is configured).

`configure_azure_monitor` installs the exporters; Microsoft Agent Framework then emits its own
GenAI spans (agent runs, model calls, MCP tool calls) and the orchestrator adds one span per
trigger with a child per router step, so each key moment is a single trace in App Insights.
"""

from __future__ import annotations

import logging

from service.settings import Settings

log = logging.getLogger("decision_lens.telemetry")


def setup_telemetry(settings: Settings) -> bool:
    if not settings.applicationinsights_connection_string:
        return False
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=settings.applicationinsights_connection_string,
        logger_name="decision_lens",
    )
    from agent_framework.observability import enable_instrumentation

    enable_instrumentation(enable_sensitive_data=False)
    log.info("telemetry -> Application Insights")
    return True
