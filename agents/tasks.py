# Celery tasks (the parallel tools)
# agents/tasks.py
from celery import shared_task

@shared_task
def run_pytest_task(repo_path):
    # Perform background tasks here
    pass
