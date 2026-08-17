import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpointEmbeddings

load_dotenv()

HF_TOKEN     = os.environ["HF_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

os.environ["HUGGINGFACEHUB_API_TOKEN"] = HF_TOKEN

hf_embedding = HuggingFaceEndpointEmbeddings(
    model="BAAI/bge-small-en-v1.5",
    huggingfacehub_api_token=HF_TOKEN,
)
