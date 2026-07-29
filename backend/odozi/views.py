# agents/views.py
# dashboard/views.py
import json
import boto3
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.parsers import JSONParser, MultiPartParser
from general.models import AuditWorkflow, AuditJob

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





class OptimizedResultsReceiverView(APIView):
    """
    Endpoint that catches the final full JSON reports sent via 'curl -F' 
    from your GitHub Actions YAML file, updating Postgres and saving logs to R2.
    """
    parser_classes = [MultiPartParser] # Optimized strictly for file uploads
    authentication_classes = [] 
    permission_classes = []

    def post(self, request, *args, **kwargs):
        # 1. Extract the tracking data parameters sent from your curl flags
        tool_name = request.data.get("tool") # e.g., 'bandit'
        repo_owner = request.data.get("repo_owner")
        
        # Clean 'owner/repo' strings safely into just the repository name
        raw_repo = request.data.get("repo", "")
        repo_name = raw_repo.split("/")[-1].strip() if "/" in raw_repo else raw_repo

        if "file" not in request.FILES:
            return Response({"error": "Missing final report file attachment"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Locate the active history rows waiting for this report in your local Postgres DB
        workflow = AuditWorkflow.objects.filter(
            repository_name=repo_name, 
            status="processing"
        ).order_by("-created_at").first()

        if not workflow:
            # Fallback check if the workflow already marked itself closed
            workflow = AuditWorkflow.objects.filter(repository_name=repo_name).order_by("-created_at").first()
            if not workflow:
                return Response({"error": "No matching active workflow history found"}, status=status.HTTP_404_NOT_FOUND)

        # Grab or allocate the individual tool tracking row
        job, _ = AuditJob.objects.get_or_create(workflow=workflow, tool_name=tool_name)

        # 3. Connect to your Cloudflare R2 client container layer
        r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        )

        uploaded_report = request.FILES["file"]
        r2_object_key = f"workspaces/{workflow.workspace_id}/workflows/{workflow.id}/jobs/{tool_name}/final_report.json"

        try:
            # 4. Decode the uploaded JSON file content safely
            report_content = uploaded_report.read().decode("utf-8")
            parsed_json = json.loads(report_content)

            # Package it uniformly for cloud storage
            final_payload = {
                "workflow_id": str(workflow.id),
                "job_id": str(job.id),
                "tool": tool_name,
                "repository": repo_name,
                "completed_at": str(datetime.now()),
                "report_data": parsed_json
            }

            # 5. Push the massive report data payload straight to Cloudflare R2 cloud storage
            r2_client.put_object(
                Bucket=settings.CLOUDFLARE_R2_BUCKET_NAME,
                Key=r2_object_key,
                Body=json.dumps(final_payload, indent=2),
                ContentType="application/json"
            )

            # 6. Save the Cloudflare file location path directly into your PostgreSQL tracking record row
            job.log_blob_path = f"{settings.CLOUDFLARE_R2_PUBLIC_URL}/{r2_object_key}"
            job.status = "success"
            job.completed_at = datetime.now()
            job.save()

            # Smart Check: If all other tool running jobs inside this workflow are done, mark the parent workflow success too!
            if not workflow.jobs.filter(status="processing").exists():
                workflow.status = "success"
                workflow.save()

            return Response({"status": "success", "message": "Final report archived safely in Cloudflare R2"}, status=status.HTTP_200_OK)

        except Exception as e:
            job.status = "failure"
            job.save()
            return Response({"error": f"Failed saving report: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


