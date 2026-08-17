# save_categories.py
# Builds the ChromaDB "categories_requirements" collection from the MySQL catalog.
# Run once (or after adding new categories).
# Secrets come from .env via database.py and embeddings.py — never hard-coded here.

import os
from langchain_chroma import Chroma
from database import get_connection
from embeddings import hf_embedding

CHROMA_PATH = "./categories"
os.makedirs(CHROMA_PATH, exist_ok=True)

vectordb = Chroma(
    persist_directory=CHROMA_PATH,
    collection_name="categories_requirements",
    embedding_function=hf_embedding,
)

db     = get_connection()
cursor = db.cursor()

cursor.execute("""
    SELECT
        c.id,
        c.name,
        GROUP_CONCAT(a.name SEPARATOR ', ')
    FROM categories c
    JOIN category_attributes ca ON c.id = ca.category_id
    JOIN attributes a           ON a.id = ca.attribute_id
    GROUP BY c.id, c.name
""")

for row in cursor.fetchall():
    category_id, category_name, attributes = str(row[0]), row[1], row[2]
    vectordb.add_texts(
        texts=[f"{category_name} requires fields: {attributes}"],
        metadatas=[{"category": category_name}],
        ids=[category_id],
    )

cursor.close()
db.close()
print("Categories saved into ChromaDB (./categories)")
