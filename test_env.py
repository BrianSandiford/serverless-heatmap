import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

print("Token:", os.getenv("OPENCELLID_TOKEN"))
