# agents/views.py
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from rest_framework import generics



class ReceiveInput(generics.CreateAPIView):
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




