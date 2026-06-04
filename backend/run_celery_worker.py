"""Script to start Celery worker from Windows."""
import os
import sys

# Add backend to Python path
backend_path = r"e:\Career coaching\100x\LDIP\backend"
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

os.chdir(backend_path)

# Now import and run celery
from celery.__main__ import main

# Run as worker with gevent pool (supports concurrent tasks)
# Use app.workers.celery instead of app.workers.celery_app
sys.argv = ['celery', '-A', 'app.workers.celery', 'worker', '--loglevel=info', '--pool=gevent', '-c', '100']
main()
