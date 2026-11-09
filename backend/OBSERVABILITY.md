# OpenTelemetry

The backend exports traces and metrics through OTLP/HTTP. Instrumentation is
disabled by default. It records Django HTTP request spans, Celery task spans,
the WebSocket-to-Celery dispatch, NeMo output-rail checks, and spans for the
project's LangChain model calls, including live prompt-regression evaluations.

LLM spans and metrics include the operation, provider, model, outcome, duration,
and token counts when the provider callback reports them. HTTP spans include the
method, response status, and route template. Celery spans include the task name
and final state. Prompt text, model output, credentials, user identifiers, task
arguments, request paths, and exception messages are not added as telemetry
attributes.

## Enable export

Run an OTLP-compatible Collector or observability service that accepts OTLP over
HTTP, then configure the backend and each Celery worker with:

```sh
export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=odozi-backend
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

The generic OTLP endpoint is the collector base URL; the HTTP exporters append
the standard `/v1/traces` and `/v1/metrics` paths. If authentication is required,
configure the exporter's standard `OTEL_EXPORTER_OTLP_HEADERS` environment
variable. Use the collector's reachable service name instead of `localhost`
when the app runs in a container or on a remote host.

Start the Django application and the Celery worker with the same telemetry
environment. For example, from `backend/`:

```sh
python manage.py runserver
celery -A odozi worker --loglevel=INFO
```

View and query the data in the configured collector/backend. This application
does not bundle a collector, storage service, or dashboard. If telemetry is
enabled without `OTEL_EXPORTER_OTLP_ENDPOINT`, startup fails with a configuration
error rather than silently dropping telemetry. When `OTEL_ENABLED` is unset or
false, no telemetry is exported.
