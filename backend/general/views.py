import io
import json
import requests
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import JSONParser, MultiPartParser, BaseParser
from rest_framework.permissions import IsAuthenticated

from django.http import JsonResponse
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse

import cloudinary
import cloudinary.uploader

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from agents.tasks import (
    add_github_result_to_pipeline,
    trigger_pipeline_follow_up_if_ready,
    get_pipeline_state
)
from .models import AuditJob
from django_python.models import ChatSession, ChatMessage
from django_python.serializer import ChatMessageSerializer


from odozi.utils.jwt_cookie_auth import HttpOnlyCookieJWTAuthentication



def health_check(request):
    return JsonResponse({"status": "ok"})

def test_endpoint(request):
    return JsonResponse({"status": "test"})


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
    Centralized polymorphic GitHub results receiver.

    Responsibilities:
    1. Receive JSON streaming chunks.
    2. Receive multipart final reports.
    3. Receive raw crash traces.
    4. Store reports in Cloudinary.
    5. AuditJob.
    6. Broadcast progress through Channels.
    7. Record completion in Redis.
    8. Trigger agentic_chat_follow_up ONLY when every expected
       GitHub tool for the orchestration has reported.
    """

    parser_classes = [JSONParser, MultiPartParser, PlainTextParser]
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        print("\n========== GITHUB RESULTS REQUEST ==========")
        print("REQUEST RECEIVED")
        print("Method:", request.method)
        print("Content-Type:", request.content_type)
        print("Headers:", dict(request.headers))
        print("============================================\n")

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

        # PHASE 1: VARIABLE EXTRACTION
        pipeline_id = None
        run_id = None
        repo_name = None
        tool_name = "pytest"
        file_content = ""
        is_crash_trace = False

        print(1111)

        # CONDITION A: JSON
        if request.content_type and request.content_type.startswith("application/json"):
            print("2222", request.data)
            pipeline_id = request.data.get("pipeline_id")
            run_id = request.data.get("run_id")
            tool_name = request.data.get("tool", "pytest")
            raw_repo = request.data.get("repo", "")
            repo_name = raw_repo.split("/")[-1].strip() if "/" in raw_repo else raw_repo
            
            logs_list = request.data.get("logs", [])
            if isinstance(logs_list, list):
                file_content = "\n".join(str(item) for item in logs_list)
            else:
                file_content = str(logs_list)

        # CONDITION B: MULTIPART FINAL REPORT
        elif request.content_type and "multipart/form-data" in request.content_type:
            print("3333", request.data)
            pipeline_id = request.data.get("pipeline_id")
            run_id = request.data.get("run_id")
            tool_name = request.data.get("tool")
            raw_repo = request.data.get("repo", "")
            repo_name = raw_repo.split("/")[-1].strip() if "/" in raw_repo else raw_repo

            if "file" in request.FILES:
                uploaded_file = request.FILES["file"]
                file_content = uploaded_file.read().decode("utf-8", errors="replace")
            else:
                file_content = ""

        # CONDITION C: RAW CRASH TRACE
        else:
            is_crash_trace = True
            file_content = str(request.data)
            pipeline_id = request.headers.get("X-Odozi-Pipeline-Id")
            run_id = request.headers.get("X-GitHub-Run-Id")

            if not run_id:
                run_id = uuid.uuid4().hex[:8]

            raw_repo = request.headers.get("X-GitHub-Repository", "unknown/repo")
            print("4444", request.data, "raw_repo", raw_repo)
            repo_name = raw_repo.split("/")[-1].strip()
            tool_name = request.headers.get("X-Odozi-Failed-Tool", "pytest")

        # VALIDATION
        if not pipeline_id:
            print("5555")
            return Response(
                {"error": "Missing pipeline_id. The GitHub workflow cannot be correlated with an active agentic pipeline."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not repo_name:
            print("6666")
            return Response(
                {"error": "Missing repository name."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # IMPORTANT PIPELINE VALIDATION
        pipeline_state = get_pipeline_state(pipeline_id)
        if not pipeline_state:
            print("7777")
            return Response(
                {"error": "Unknown or expired pipeline_id.", "pipeline_id": pipeline_id},
                status=status.HTTP_404_NOT_FOUND,
            )

        # The existing pipeline AuditJob stores the final LLM summary. Create
        # one additional AuditJob for this exact tool/run to retain all tests.
        auditjob_id = pipeline_state.get("auditjob_id")
        if not run_id:
            run_id = uuid.uuid4().hex
        result_auditjob, _ = AuditJob.objects.get_or_create(
            pipeline_id=pipeline_id,
            tool_name=tool_name or "unknown",
            run_id=str(run_id),
        )

        # CLOUDINARY STORAGE
        cloudinary_public_id = (
            f"auditjobs/{pipeline_id}/jobs/{tool_name}/{run_id}/final_report.json"
        )

        try:
            payload_data_block = json.loads(file_content)
        except Exception:
            payload_data_block = {"raw_terminal_stdout_stream": file_content.splitlines()}

        final_cloudinary_payload = {
            "auditjob_id": str(result_auditjob.id),
            "pipeline_auditjob_id": str(auditjob_id) if auditjob_id else None,
            "tool": tool_name,
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "content": payload_data_block,
        }

        cloudinary_url = None
        try:
            cloudinary_upload = cloudinary.uploader.upload(
                io.BytesIO(json.dumps(final_cloudinary_payload, indent=2).encode("utf-8")),
                resource_type="raw",
                type="upload",
                public_id=cloudinary_public_id,
                overwrite=True,
            )
            cloudinary_url = cloudinary_upload.get("secure_url")
        except Exception as upload_err:
            print(f"⚠️ Cloudinary upload warning: {upload_err}")

        # Save the Cloudinary URL on this test's own AuditJob row.
        if cloudinary_url:
            result_auditjob.log_blob_path = cloudinary_url
            result_auditjob.save(update_fields=["log_blob_path"])

        job_status = "failure" if is_crash_trace else "success"

        # WEBSOCKET PROGRESS
        channel_layer = get_channel_layer()
        channel_name = pipeline_state.get("channel_name")
        if channel_layer and channel_name:
            styled_logs = [
                "",
                "┌──────────────────────────────────────────────────────────┐",
                f"  ► INGESTION PIPELINE PARSER ARCHIVE SECURED: {tool_name.upper()}",
                f"  ► STATUS ENGINE COMPLETION DETERMINISTIC: [ {job_status.upper()} ]",
                "└──────────────────────────────────────────────────────────┘",
                "",
            ]

            async_to_sync(channel_layer.group_send)(
                channel_name,
                {
                    "type": "chat_message",
                    "payload": {
                        "type": "status",
                        "message": f"Completed {tool_name} processing engine loop context.",
                        "live_logs": styled_logs,
                        "tool": tool_name,
                        "pipeline_id": pipeline_id,
                    },
                },
            )

        # REDIS RESULT
        github_result = {
            "status": job_status,
            "scope_status": job_status,
            "tool": tool_name,
            "repo": repo_name,
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "auditjob_id": str(result_auditjob.id),
            "pipeline_auditjob_id": str(auditjob_id) if auditjob_id else None,
            "cloudinary_public_id": cloudinary_public_id,
            "cloudinary_url": cloudinary_url,
            "content": payload_data_block,
        }

        # The Redis completion gate decides when to launch the follow-up.
        added = add_github_result_to_pipeline(
            pipeline_id=pipeline_id,
            repository=repo_name,
            tool=tool_name,
            result=github_result,
        )

        follow_up_started = trigger_pipeline_follow_up_if_ready(pipeline_id)

        # FINAL RESPONSE
        return Response(
            {
                "status": "processed",
                "scope_status": job_status,
                "pipeline_id": pipeline_id,
                "tool": tool_name,
                "auditjob_id": str(result_auditjob.id),
                "pipeline_auditjob_id": str(auditjob_id) if auditjob_id else None,
                "result_recorded": added,
                "follow_up_started": follow_up_started,
                "message": f"Final {tool_name} result received and recorded.",
            },
            status=status.HTTP_200_OK,
        )

            

class CloudinaryHistoryReportView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pipeline_id):
        auditjobs = AuditJob.objects.filter(
            pipeline_id=pipeline_id,
            log_blob_path__isnull=False,
        ).exclude(log_blob_path="").order_by("created_at")

        if not auditjobs.exists():
            return Response({"error": "AuditJob not found."}, status=status.HTTP_404_NOT_FOUND)

        reports = []
        for auditjob in auditjobs:
            item = {
                "auditjob_id": str(auditjob.id),
                "tool": auditjob.tool_name,
                "run_id": auditjob.run_id,
                "cloudinary_url": auditjob.log_blob_path,
            }
            try:
                response = requests.get(auditjob.log_blob_path, timeout=30)
                if response.status_code != 200:
                    item.update({
                        "error": "Cloudinary report could not be retrieved.",
                        "cloudinary_status": response.status_code,
                    })
                else:
                    try:
                        item["report"] = response.json()
                    except ValueError:
                        item["report"] = response.text
            except requests.RequestException as error:
                item.update({"error": "Failed to contact Cloudinary.", "details": str(error)})
            reports.append(item)

        return Response({
            "pipeline_id": str(pipeline_id),
            "count": len(reports),
            "reports": reports,
        }, status=status.HTTP_200_OK)



class ChatHistoryReportView(APIView):
    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request,session):
        print(request.user, "kenyaaaaaaa", session)
        chat_session  = ChatSession.objects.prefetch_related("messages").get(pk=session, user=request.user)
        serializer = ChatMessageSerializer(
            chat_session.messages.all(),
            many=True,
        )
        print(serializer.data)

        return Response({
            "id": chat_session.id,
            "messages": serializer.data,
        })


