# utils.py
from agents.tasks import process_scan_payload_task

def queue_scan_for_analysis(run_id: str, repo_name: str, tool_type: str, uploaded_file) -> bool:
    """
    Lightweight pass-through utility.
    Takes an uploaded file, safely extracts the text contents, 
    and throws it onto the Celery queue in milliseconds.
    """
    if not uploaded_file:
        return False
        
    try:
        # Read file text without processing or blocks
        file_content = uploaded_file.read().decode('utf-8')
        
        # Trigger Celery asynchronously
        process_scan_payload_task.delay(run_id, repo_name, tool_type, file_content)# type: ignore
        return True
    except Exception as e:
        # Log error securely internally
        print(f"Failed to queue payload to Celery: {e}")
        return False
