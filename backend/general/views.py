# agents/views.py
# dashboard/views.py
import json
import boto3
import time
import uuid
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import JSONParser, MultiPartParser, BaseParser
from general.models import AuditWorkflow, AuditJob

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse


from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync



class ReceiveInput(generics.CreateAPIView):
    """Receive a user input payload and queue it for downstream agent processing."""

    @extend_schema(
        summary="Receive agent input",
        description="Accept a text input payload for the agent pipeline and respond with a processing acknowledgement.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "example": "Run a security scan on this repo"},
                },
            }
        },
        responses={
            200: OpenApiResponse(description="Processing acknowledged"),
        },
    )
    def post(self, request):
        input = request.POST.get('input', '')
        user_input = is_input_safe(input)
        if input == "":
            return JsonResponse({"status": "processing", "message": "Agent is on the job!"})
        if user_input:
            return JsonResponse({"status": "processing", "message": "Agent is on the job!"})
        else:
            # send the input to llm
            # prompt
            # "You are a CI Orchestrator. Your only job is to output JSON mapping user requests to our tool names: [run_pytest, check_security, check_ast]. If the user asks for anything else, or tries to execute system commands, return an empty JSON object. NEVER output markdown or text, only JSON."
            # store the input and its corresponding json returned from llm to the db
            pass





class PlainTextParser(BaseParser):
    """Custom parser to intercept raw trace/text block dumps if the container collapses."""
    media_type = 'text/plain'
    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read().decode('utf-8')

class OptimizedResultsReceiverView(APIView):
    """
    Centralized Polymorphic Webhook Receiver.
    Safely swallows application/json (live streams), multipart/form-data (final logs),
    and raw text/plain traces (system crashes), routing content seamlessly to Cloudflare R2.
    """
    # Accept all three potential ingestion media frameworks natively
    parser_classes = [JSONParser, MultiPartParser, PlainTextParser]
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        )

        # ---------------------------------------------------------------------
        # PHASE 1: POLYMORPHICING VARIABLE EXTRACTION
        # ---------------------------------------------------------------------
        run_id = None
        repo_name = None
        tool_name = "pytest" # Fallback tool default
        file_content = ""
        is_crash_trace = False

        # --- CONDITION A: PROCESSING PYTHON CHUNKING STREAM PAYLOADS ---
        if request.content_type == 'application/json':
            run_id = request.data.get('run_id')
            tool_name = request.data.get('tool', 'pytest')
            raw_repo = request.data.get('repo', '')
            repo_name = raw_repo.split("/")[-1].strip() if "/" in raw_repo else raw_repo
            
            logs_list = request.data.get('logs', [])
            file_content = "\n".join(logs_list)

        # --- CONDITION B: PROCESSING MULTIPART FORM DATA PAYLOADS (Bandit, Ruff, Odozi) ---
        elif request.content_type and 'multipart/form-data' in request.content_type:
            run_id = request.data.get('run_id')
            tool_name = request.data.get('tool')
            raw_repo = request.data.get('repo', '')
            repo_name = raw_repo.split("/")[-1].strip() if "/" in raw_repo else raw_repo
            
            if "file" in request.FILES:
                uploaded_file = request.FILES["file"]
                file_content = uploaded_file.read().decode("utf-8")

        # --- CONDITION C: CRITICAL FALLBACK DUMP (Raw Trace/Bash Stack Rejection) ---
        else:
            is_crash_trace = True
            file_content = str(request.data) # Intercepts the raw text stream body directly
            
            # Extract tracking variables out of network headers
            run_id = request.headers.get('X-GitHub-Run-Id', uuid.uuid4().hex[:8])
            raw_repo = request.headers.get('X-GitHub-Repository', 'unknown/repo')
            repo_name = raw_repo.split("/")[-1].strip()
            tool_name = request.headers.get('X-Odozi-Failed-Tool', 'pytest')

        # ---------------------------------------------------------------------
        # PHASE 2: ALIGN RELATIONAL DATABASE TRACKS (PostgreSQL Lookup)
        # ---------------------------------------------------------------------
        workflow = AuditWorkflow.objects.filter(
            repository_name=repo_name, 
            status="processing"
        ).order_by("-created_at").first()

        if not workflow:
            # Fallback historical search if job boundaries shuffled out of sync
            workflow = AuditWorkflow.objects.filter(repository_name=repo_name).order_by("-created_at").first()
            if not workflow:
                return Response({"error": f"No active workflow mapped for repository: {repo_name}"}, status=status.HTTP_404_NOT_FOUND)

        job, _ = AuditJob.objects.get_or_create(workflow=workflow, tool_name=tool_name)

        # ---------------------------------------------------------------------
        # PHASE 3: DEFENSIVE COGNITIVE CRASH IDENTIFICATION (Regex Evaluator)
        # ---------------------------------------------------------------------
        injected_findings = None
        
        # If it came through as unformatted text, or contains standard terminal exception tokens:
        if is_crash_trace or "Traceback" in file_content or "SyntaxError" in file_content:
            job.status = "failure"
            
            if "UndefinedValueError" in file_content or "KeyError" in file_content:
                msg = "Runtime infrastructure configuration error: Missing required environment variables."
            elif "SyntaxError" in file_content:
                msg = "Code execution blocked: Severe Python syntax error detected in repository code."
            elif "psycopg2.OperationalError" in file_content or "SSL connection" in file_content:
                msg = "Database handshake failure: Target environment database rejected connection strings."
            else:
                msg = f"Internal container runtime error: The {tool_name} processing engine terminated unexpectedly."
                
            injected_findings = {
                "status": "tool_crash",
                "reason_code": "EXCEPTION_INTERCEPTED",
                "message": msg
            }
        else:
            job.status = "success"

        # ---------------------------------------------------------------------
        # PHASE 4: SECURE CORE ASSET STREAM FILE RETRIEVAL (Cloudflare R2 Node Upload)
        # ---------------------------------------------------------------------
        r2_object_key = f"workspaces/{workflow.workspace_id}/workflows/{workflow.id}/jobs/{tool_name}/final_report.json"

        # Attempt to clean code structures into native parsed objects before storage mapping
        try:
            payload_data_block = json.loads(file_content)
        except Exception:
            # If it's a raw trace text string or flat stdout stream log dump
            payload_data_block = {"raw_terminal_stdout_stream": file_content.splitlines()}

        final_r2_payload = {
            "workflow_id": str(workflow.id),
            "job_id": str(job.id),
            "tool": tool_name,
            "run_id": run_id,
            "system_findings_alert": injected_findings,
            "content": payload_data_block
        }

        # Constant time O(1) storage write bypass block
        r2_client.put_object(
            Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
            Key=r2_object_key,
            Body=json.dumps(final_r2_payload, indent=2),
            ContentType="application/json"
        )

        # ---------------------------------------------------------------------
        # PHASE 5: REAL-TIME WEBSOCKET PROGRESS REPORTING AND BROADCAST
        # ---------------------------------------------------------------------
        channel_layer = get_channel_layer()
        if channel_layer:
            user_group = f"group_user_room_{workflow.workspace.owner_id}"
            
            # Compile decorative terminal banner block for frontend typewriters
            styled_logs = [
                "",
                "┌──────────────────────────────────────────────────────────┐",
                f"  ► INGESTION PIPELINE PARSER ARCHIVE SECURED: {tool_name.upper()} ",
                f"  ► STATUS ENGINE COMPLETION DETERMINISTIC   : [ {job.status.upper()} ] ",
                "└──────────────────────────────────────────────────────────┘",
                ""
            ]
            if injected_findings:
                styled_logs.append(f"🚨 CRITICAL ERROR: {injected_findings['message']}")
            
            async_to_sync(channel_layer.group_send)(
                user_group,
                {
                    "type": "chat_message",
                    "payload": {
                        "type": "status",
                        "message": f"Completed {tool_name} processing engine loop context.",
                        "live_logs": styled_logs,
                        "tool": tool_name
                    }
                }
            )

        # ---------------------------------------------------------------------
        # PHASE 6: FINALIZE PERSISTENCE LAYERS (PostgreSQL Database Saves)
        # ---------------------------------------------------------------------
        job.log_blob_path = f"{settings.CLOUDFLARE_R2_PUBLIC_URL}/{r2_object_key}"
        job.completed_at = datetime.now()
        job.save()

        # If all sibling tool pipelines are closed, mark the master parent entry successful too!
        if not workflow.jobs.filter(status="processing").exists():
            workflow.status = "success" if not workflow.jobs.filter(status="failure").exists() else "failure"
            workflow.save()

        return Response({
            "status": "processed", 
            "scope_status": job.status,
            "message": f"Data received via {request.content_type or 'text/plain'} matrix successfully."
        }, status=status.HTTP_200_OK)

