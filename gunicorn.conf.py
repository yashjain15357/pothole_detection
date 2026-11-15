import os

# Automatically bind to Render's injected PORT environment variable
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

workers = 2
timeout = 120
max_requests = 500
max_requests_jitter = 50
