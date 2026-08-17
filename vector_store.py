from langchain_chroma import Chroma
from embeddings import hf_embedding

categories_db = Chroma(
    persist_directory="./categories",
    collection_name="categories_requirements",
    embedding_function=hf_embedding
)

products_db = Chroma(
    persist_directory="./products_store",
    collection_name="products",
    embedding_function=hf_embedding
)
