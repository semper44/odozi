# agents/views.py
# dashboard/views.py
import json
import boto3
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import JSONParser, MultiPartParser
from .models import AuditWorkflow, AuditJob

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse



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
    def post(self, reqqust):
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





class OptimizedResultsReceiverView(APIView):
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request, *args, **kwargs):
        tool_name = request.data.get("tool")
        repo_name = request.data.get("repo", "").split("/")[-1].strip()
        run_id = request.data.get("run_id") # GitHub Run ID token identifier

        # Fetch the matching operational database tracking rows
        workflow = AuditWorkflow.objects.filter(repository_name=repo_name, status="processing").order_by("-created_at").first()
        if not workflow:
            return Response({"status": "ignored", "reason": "No active workflow model context"}, status=status.HTTP_200_OK)

        job, _ = AuditJob.objects.get_or_create(workflow=workflow, tool_name=tool_name)

        r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        )

        # 🌟 ADJUSTMENT A: ATOMIC LOG STREAM CHUNKING (Pytest Streamer)
        if "logs" in request.data:
            log_lines = request.data.get("logs", [])
            if not log_lines:
                return Response({"status": "empty"}, status=status.HTTP_200_OK)

            # Generate an isolated file segment chunk using a timestamp token hash identifier
            # Path layout: workspaces/{id}/workflows/{id}/jobs/{tool}/chunk_{timestamp}.json
            timestamp_token = int(time.time_ns())
            chunk_object_key = f"workspaces/{workflow.workspace_id}/workflows/{workflow.id}/jobs/{tool_name}/chunk_{timestamp_token}.json"

            chunk_payload = {
                "run_id": run_id,
                "sequence_timestamp": timestamp_token,
                "lines": log_lines
            }

            # Direct $O(1)$ write operation. Zero reads, zero race conditions, zero file overrides!
            r2_client.put_object(
                Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
                Key=chunk_object_key,
                Body=json.dumps(chunk_payload),
                ContentType="application/json"
            )
            return Response({"status": "chunk_filed"}, status=status.HTTP_200_OK)

        # 🌟 ADJUSTMENT B: STRUCTURAL COMPLETED REPORTS (Bandit / Ruff / Odozi)
        elif "file" in request.FILES:
            uploaded_report = request.FILES["file"]
            final_report_key = f"workspaces/{workflow.workspace_id}/workflows/{workflow.id}/jobs/{tool_name}/final_report.json"

            try:
                report_data = json.loads(uploaded_report.read().decode("utf-8"))
                
                r2_client.put_object(
                    Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
                    Key=final_report_key,
                    Body=json.dumps({"tool": tool_name, "run_id": run_id, "data": report_data}, indent=2),
                    ContentType="application/json"
                )

                # Link history path mapping pointer to PostgreSQL row index
                job.log_blob_path = f"jobs/{tool_name}/" # Store parent folder prefix directory path reference
                job.status = "success"
                job.completed_at = datetime.now()
                job.save()

                return Response({"status": "report_filed"}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"error": "Malformed structural payload parameter data wrapper"}, status=status.HTTP_400_BAD_REQUEST)



