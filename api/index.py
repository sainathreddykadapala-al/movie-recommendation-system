import os
import sys

# Ensure root directory is on Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Explicitly flag serverless environment
os.environ['VERCEL'] = '1'

from app import app

