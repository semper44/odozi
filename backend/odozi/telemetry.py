import atexit
import inspect
import logging
import os
import time
from contextlib import contextmanager
from threading import Lock
from typing import Any, Generator

from asgiref.sync import markcoroutinefunction
from celery.signals import before_task_publish, task_failure, task_postrun, task_prerun
from opentelemetry import context, metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode


logger = logging.getLogger(__name__)
_INITIALIZED = False
_INITIALIZATION_LOCK = Lock()
_TASK_SPANS: dict[str, tuple[Span, Any]] = {}
_TASK_SPANS_LOCK = Lock()
_LLM_METRICS: tuple[Any, Any, Any] | None = None
_HTTP_METRICS: tuple[Any, Any] | None = None
_METRICS_LOCK = Lock()


def _telemetry_enabled() -> bool:
    return os.getenv("OTEL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def setup_telemetry() -> bool:
    """Configure OTLP exporters and trace Celery task execution in this process."""
    global _INITIALIZED
    if not _telemetry_enabled():
        return False

    with _INITIALIZATION_LOCK:
        if _INITIALIZED:
            return True

        if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
            raise RuntimeError(
                "OTEL_ENABLED is true but OTEL_EXPORTER_OTLP_ENDPOINT is not configured."
            )

        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "odozi-backend"),
                "deployment.environment.name": os.getenv(
                    "ENVIRONMENT", "development"
                ),
            }
        )

        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        atexit.register(tracer_provider.shutdown)
        atexit.register(meter_provider.shutdown)

        before_task_publish.connect(_inject_task_trace_context, weak=False)
        task_prerun.connect(_start_task_span, weak=False)
        task_failure.connect(_mark_task_failed, weak=False)
        task_postrun.connect(_finish_task_span, weak=False)

        _INITIALIZED = True
        logger.info(
            "OpenTelemetry enabled for service %s",
            resource.attributes["service.name"],
        )
        return True


def _inject_task_trace_context(
    headers: dict[str, Any] | None = None,
    **_: Any,
) -> None:
    if headers is not None:
        propagate.inject(headers)


def _start_task_span(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **_: Any,
) -> None:
    if not task_id or task is None:
        return

    task_name = getattr(task, "name", None) or getattr(sender, "name", "unknown")
    request = getattr(task, "request", None)
    parent_context = propagate.extract(getattr(request, "headers", None) or {})
    span = trace.get_tracer("odozi.celery").start_span(
        "celery.task",
        context=parent_context,
        attributes={"celery.task.name": str(task_name)},
        record_exception=False,
        set_status_on_exception=False,
    )
    token = context.attach(trace.set_span_in_context(span, parent_context))
    with _TASK_SPANS_LOCK:
        _TASK_SPANS[task_id] = (span, token)


def _mark_task_failed(
    task_id: str | None = None,
    exception: BaseException | None = None,
    **_: Any,
) -> None:
    if not task_id:
        return
    with _TASK_SPANS_LOCK:
        active = _TASK_SPANS.get(task_id)
    if active is not None:
        span, _ = active
        span.set_attribute(
            "error.type",
            type(exception).__name__ if exception is not None else "TaskFailure",
        )
        span.set_status(Status(StatusCode.ERROR))


def _finish_task_span(
    task_id: str | None = None,
    state: str | None = None,
    **_: Any,
) -> None:
    if not task_id:
        return
    with _TASK_SPANS_LOCK:
        active = _TASK_SPANS.pop(task_id, None)
    if active is None:
        return

    span, token = active
    if state:
        span.set_attribute("celery.task.state", state)
    if state in {"FAILURE", "REVOKED"}:
        span.set_status(Status(StatusCode.ERROR))
    span.end()
    context.detach(token)


def _llm_metrics() -> tuple[Any, Any, Any]:
    global _LLM_METRICS
    if _LLM_METRICS is None:
        with _METRICS_LOCK:
            if _LLM_METRICS is None:
                meter = metrics.get_meter("odozi.llm")
                _LLM_METRICS = (
                    meter.create_counter("odozi.llm.calls", unit="{call}"),
                    meter.create_counter("odozi.llm.tokens", unit="{token}"),
                    meter.create_histogram("odozi.llm.duration", unit="s"),
                )
    return _LLM_METRICS


@contextmanager
def llm_call(
    operation: str, provider: str, model: str
) -> Generator[Span, None, None]:
    """Trace an LLM call without recording prompts, completions, or credentials."""
    calls, _, duration = _llm_metrics()
    attributes = {
        "llm.operation": operation,
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
    }
    started_at = time.perf_counter()
    outcome = "success"

    with trace.get_tracer("odozi.llm").start_as_current_span(
        f"llm.{operation}",
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception as exc:
            outcome = "error"
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            elapsed = time.perf_counter() - started_at
            metric_attributes = {**attributes, "outcome": outcome}
            calls.add(1, metric_attributes)
            duration.record(elapsed, metric_attributes)
            span.set_attribute("llm.duration_ms", elapsed * 1000)


def record_llm_tokens(
    span: Span,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Record token counts when the provider callback reports them."""
    _, tokens, _ = _llm_metrics()
    attributes = {
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
    }

    if prompt_tokens > 0:
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
        tokens.add(prompt_tokens, {**attributes, "token.type": "input"})
    if completion_tokens > 0:
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
        tokens.add(completion_tokens, {**attributes, "token.type": "output"})


def _http_metrics() -> tuple[Any, Any]:
    global _HTTP_METRICS
    if _HTTP_METRICS is None:
        with _METRICS_LOCK:
            if _HTTP_METRICS is None:
                meter = metrics.get_meter("odozi.http")
                _HTTP_METRICS = (
                    meter.create_counter("odozi.http.server.requests", unit="{request}"),
                    meter.create_histogram("odozi.http.server.duration", unit="s"),
                )
    return _HTTP_METRICS


def _request_route(request: Any) -> str | None:
    match = getattr(request, "resolver_match", None)
    route = getattr(match, "route", None)
    return route if isinstance(route, str) else None


def _record_http_request(
    request: Any,
    span: Span,
    started_at: float,
    status_code: int,
) -> None:
    method = str(getattr(request, "method", "UNKNOWN"))
    route = _request_route(request)
    attributes: dict[str, str | int] = {
        "http.request.method": method,
        "http.response.status_code": status_code,
    }
    if route:
        attributes["http.route"] = route
        span.set_attribute("http.route", route)
        span.update_name(f"{method} {route}")

    span.set_attribute("http.request.method", method)
    span.set_attribute("http.response.status_code", status_code)
    requests, duration = _http_metrics()
    requests.add(1, attributes)
    duration.record(time.perf_counter() - started_at, attributes)


class OpenTelemetryRequestMiddleware:
    """Create privacy-conscious HTTP server spans for Django requests."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Any):
        self.get_response = get_response
        self._is_async = inspect.iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def __call__(self, request: Any) -> Any:
        if self._is_async:
            return self._call_async(request)
        return self._call_sync(request)

    def _start_span(self, request: Any) -> tuple[Any, float]:
        method = str(getattr(request, "method", "UNKNOWN"))
        started_at = time.perf_counter()
        span = trace.get_tracer("odozi.http").start_span(
            f"HTTP {method}",
            attributes={"http.request.method": method},
            record_exception=False,
            set_status_on_exception=False,
        )
        return span, started_at

    def _finish_span(
        self, request: Any, span: Span, started_at: float, status_code: int
    ) -> None:
        _record_http_request(request, span, started_at, status_code)
        span.end()

    def _call_sync(self, request: Any) -> Any:
        span, started_at = self._start_span(request)
        token = context.attach(trace.set_span_in_context(span))
        try:
            response = self.get_response(request)
        except BaseException as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR))
            self._finish_span(request, span, started_at, 500)
            raise
        else:
            self._finish_span(
                request,
                span,
                started_at,
                int(getattr(response, "status_code", 500)),
            )
            return response
        finally:
            context.detach(token)

    async def _call_async(self, request: Any) -> Any:
        span, started_at = self._start_span(request)
        token = context.attach(trace.set_span_in_context(span))
        try:
            response = await self.get_response(request)
        except BaseException as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR))
            self._finish_span(request, span, started_at, 500)
            raise
        else:
            self._finish_span(
                request,
                span,
                started_at,
                int(getattr(response, "status_code", 500)),
            )
            return response
        finally:
            context.detach(token)


@contextmanager
def trace_span(
    name: str, attributes: dict[str, Any] | None = None
) -> Generator[Span, None, None]:
    """Create a span for a non-LLM operation without capturing exception text."""
    with trace.get_tracer("odozi").start_as_current_span(
        name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR))
            raise
