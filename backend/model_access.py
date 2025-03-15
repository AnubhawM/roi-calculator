from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = OpenAI()

# Set your API key

# List available models
models = client.models.list()
for model in models.data:
    print(model)
