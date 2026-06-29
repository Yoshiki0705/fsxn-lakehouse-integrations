"""Lambda entry point for OpenSharing Volumes server.

Uses Mangum to adapt FastAPI to Lambda + Function URL / API Gateway.
"""

from mangum import Mangum
from src.server import app

handler = Mangum(app, lifespan="off")
