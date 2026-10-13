import uvicorn
import os
import subprocess
import platform
from dotenv import load_dotenv

load_dotenv()

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if __name__ == "__main__":
    print(f"Starting HealthLete IQ API on {API_HOST}:{API_PORT} [{ENVIRONMENT}]...")
    
    # Gunicorn does not support Windows natively. 
    # Use standard Uvicorn on Windows, or when in development mode.
    if ENVIRONMENT == "development" or platform.system() == "Windows":
        uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=True)
    else:
        # Run Gunicorn + Uvicorn Workers in Production
        workers = os.getenv("WORKERS", "4")
        cmd = [
            "gunicorn", 
            "app.main:app",
            "--workers", workers,
            "--worker-class", "uvicorn.workers.UvicornWorker",
            "--bind", f"{API_HOST}:{API_PORT}"
        ]
        print(f"Running Gunicorn: {' '.join(cmd)}")
        subprocess.run(cmd)
