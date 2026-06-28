# agents/views.py
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from rest_framework import generics
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




