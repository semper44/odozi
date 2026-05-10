# The logic that calls the LLM and triggers tasks
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def github_webhook(request):
    if request.method == "POST":
        payload = json.loads(request.body)
        print(payload)
        return JsonResponse({"status": "received"})
    
    return JsonResponse({"error": "invalid"}, status=400)