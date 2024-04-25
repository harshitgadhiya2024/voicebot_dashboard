"""
    Setup enviroment variable value
"""
import os
from dotenv import load_dotenv

load_dotenv()

enviroment = {
    "prod": {
        "Mongourl": os.getenv("mongourl"),
    }
}
