import os

# Automatically bind to Render's injected PORT environment variable
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

workers = 1
timeout = 300
max_requests = 100
max_requests_jitter = 20
