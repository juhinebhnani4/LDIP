# Start Celery worker for LDIP backend
Set-Location "e:\Career coaching\100x\LDIP\backend"
$env:PYTHONPATH = "e:\Career coaching\100x\LDIP\backend"

Write-Host "Starting Celery worker with solo pool (Windows compatible)..."
& "e:\Career coaching\100x\LDIP\.venv\Scripts\python.exe" -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo
