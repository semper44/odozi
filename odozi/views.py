# agents/views.py
from django.http import JsonResponse
from agents.orchestrator import start_agentic_workflow
import re


def is_input_safe(user_text):
    # Block common shell injection characters
    forbidden_chars = [";", "&&", "||", ">", "<", "|", "$(", "{"]
    if any(char in user_text for char in forbidden_chars):
        return True
    return False

def github_webhook(request):
    # 1. Get GitHub data
    repo_url = request.POST.get('repo_url')
    branch = request.POST.get('branch')


    # 2. Kick off the orchestrator
    # We don't 'await' this; it starts the background process and returns 200 OK
    start_agentic_workflow(repo_url, branch)

    return JsonResponse({"status": "processing", "message": "Agent is on the job!"})

class ReceiveInput(generics.PostAPIView):
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




