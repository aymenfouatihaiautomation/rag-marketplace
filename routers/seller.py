from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import PromptTemplate

from embeddings import GROQ_API_KEY
from vector_store import categories_db, products_db
from database import get_connection
from routers.auth import get_current_user

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────
class UserMessage(BaseModel):
    message: str

class ProductData(BaseModel):
    name: str
    description: str
    price: float
    stock: int

class BotResponse(BaseModel):
    action: Literal["CHAT", "NO_MATCH", "CONFIRM_CATEGORY", "UNCLEAR_CONFIRMATION", "COLLECT_FIELDS", "SAVE_PRODUCT"]
    category: str | None
    response: str
    product_data: ProductData | None = None


# ── LLM ───────────────────────────────────────────────────────────────────────
llm            = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3, groq_api_key=GROQ_API_KEY)
structured_llm = llm.with_structured_output(BotResponse)


# ── Prompt ─────────────────────────────────────────────────────────────────────
PROMPT = PromptTemplate(
    input_variables=["locked_category", "pending_category", "requirements", "candidates", "chat_history", "user_message"],
    template="""
You are a strict and precise assistant for a tech shop that helps sellers add products to inventory.

## SESSION STATE
- Locked category  : {locked_category}
- Pending category : {pending_category}
- Required fields  : {requirements}

## CANDIDATE CATEGORIES
{candidates}

## CHAT HISTORY
{chat_history}

## USER MESSAGE
{user_message}

## RULES

### RULE 0 — PRODUCT NAME (CRITICAL)
NEVER ask the user for the product name. NEVER include "name" or "nom" in your questions.
The product name will be auto-constructed from Marque + Modèle collected during field collection.
Example: Marque=Apple, Modèle=iPhone 15 → name = "Apple iPhone 15"

### RULE 1 — FIELD VALIDATION (CRITICAL)
Before accepting any value for a field, verify it is semantically coherent:
- "Prix" must be a positive number (e.g. 999, 49.99). Reject words, colors, letters.
- "Stock" must be a positive integer (e.g. 10, 50). Reject anything that is not a whole number.
- "Processeur" must be a real processor name (e.g. Apple A17, Intel i7). Reject colors, random words.
- "RAM" must be a memory size (e.g. 8GB, 16GB). Reject anything else.
- "Stockage" must be a storage size (e.g. 256GB, 1TB). Reject anything else.
- "Marque" must be a real brand name. Reject generic words.
- "Modèle" must be a real product model. Reject random words.
- Apply the same logic to all other fields: the value must make real-world sense for that field.

If the value is incoherent or invalid: reject it clearly, explain briefly why, and ask for the correct value again.
Do NOT move to the next field until the current one has a valid value.

### RULE 2 — PRIX AND STOCK ARE ALWAYS MANDATORY
"Prix" and "Stock" are ALWAYS required for every product, regardless of what the required fields list says.
NEVER fire SAVE_PRODUCT if Prix or Stock are missing or equal to 0.
Always ask for Prix and Stock if they have not been provided with valid values.

### RULE 3 — COLLECTING FIELDS
If locked_category is set:
  - Scan the chat history to find which required fields already have VALID values.
  - Ask for the next missing field ONE AT A TIME.
  - Do NOT skip any field. Do NOT ask for the product name (see RULE 0).
  - Once ALL required fields including Prix and Stock have valid values:
    → action: SAVE_PRODUCT
    → Construct name automatically as: "{{Marque}} {{Modèle}}" from collected values.
    → Build a natural description from all other collected attributes.
    → Set price from the collected Prix value (as float).
    → Set stock from the collected Stock value (as int).
    → Write a success confirmation in response.
  - Otherwise → action: COLLECT_FIELDS

### RULE 4 — CATEGORY CONFIRMATION
If pending_category is set:
  - User confirms  → lock category, start collecting fields.   action: COLLECT_FIELDS
  - User denies    → ask to re-describe.                       action: CHAT
  - Unclear        → ask yes/no again.                         action: UNCLEAR_CONFIRMATION

### RULE 5 — NO CATEGORY YET
If no category is locked or pending:
  - User is chatting / not selling → nudge toward selling.     action: CHAT
  - Good match in candidates       → ask to confirm.           action: CONFIRM_CATEGORY
  - No match                       → tell the user.            action: NO_MATCH

Only fill product_data when action is SAVE_PRODUCT. Leave it null otherwise.
"""
)


# ── Per-user session store ─────────────────────────────────────────────────────
user_sessions: dict[int, dict] = {}

def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "session_state": {
                "category": None,
                "requirements": [],
                "pending_category": None,
                "pending_requirements": []
            },
            "chat_history": ChatMessageHistory()
        }
    return user_sessions[user_id]


# ── Helpers ────────────────────────────────────────────────────────────────────
def parse_attributes(text: str) -> list[str]:
    marker = "requires fields:"
    if marker in text:
        return [f.strip() for f in text.split(marker, 1)[1].split(",") if f.strip()]
    return []

def search_categories(query: str) -> list[dict]:
    results = categories_db.similarity_search(query, k=3)
    return [
        {"category": doc.metadata["category"], "requirements": parse_attributes(doc.page_content)}
        for doc in results if doc.metadata.get("category")
    ]


# ── Save product to MySQL + ChromaDB ──────────────────────────────────────────
def save_product(product: ProductData, category: str, user_id: int) -> int:
    # 1. MySQL
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, description, category, price, stock, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (product.name, product.description, category, product.price, product.stock, user_id)
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()

    # 2. ChromaDB
    document = (
        f"Name: {product.name}\n"
        f"Category: {category}\n"
        f"Price: {product.price}€\n"
        f"Stock: {product.stock}\n"
        f"Description: {product.description}"
    )
    products_db.add_texts(
        texts=[document],
        metadatas=[{
            "name":     product.name,
            "category": category,
            "price":    str(product.price),
            "stock":    str(product.stock)
        }],
        ids=[str(new_id)]
    )
    return new_id


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/seller/chat")
async def seller_chat(user_msg: UserMessage, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    session = get_session(user_id)
    ss      = session["session_state"]
    history = session["chat_history"]
    query   = user_msg.message

    history_str = "\n".join(
        f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}"
        for m in history.messages
    ) or "No history yet."

    candidates      = search_categories(query)
    candidates_text = "\n".join(f"- {c['category']}" for c in candidates) or "None found."

    result: BotResponse = structured_llm.invoke(PROMPT.format(
        locked_category  = ss["category"] or "null",
        pending_category = ss["pending_category"] or "null",
        requirements     = ", ".join(ss["requirements"]) or "none",
        candidates       = candidates_text,
        chat_history     = history_str,
        user_message     = query,
    ))

    saved_product_id = None

    if result.action == "CONFIRM_CATEGORY":
        matched = next((c for c in candidates if c["category"] == result.category), None)
        ss["pending_category"]     = result.category
        ss["pending_requirements"] = matched["requirements"] if matched else []

    elif result.action == "COLLECT_FIELDS" and ss["category"] is None:
        ss["category"]             = ss["pending_category"]
        ss["requirements"]         = ss["pending_requirements"]
        ss["pending_category"]     = None
        ss["pending_requirements"] = []

    elif result.action == "SAVE_PRODUCT" and result.product_data is not None:
        saved_product_id = save_product(result.product_data, ss["category"], user_id)
        # FIX: reset state and clear history BEFORE adding new messages
        # so the next turn starts completely fresh with no stale context
        ss.update({"category": None, "requirements": [], "pending_category": None, "pending_requirements": []})
        history.clear()
        # Add only the AI confirmation — skip the raw user data message
        history.add_ai_message(result.response)
        return {
            "category_detected": None,
            "pending_category":  None,
            "required_fields":   [],
            "saved_product_id":  saved_product_id,
            "response":          result.response
        }

    elif result.action in ("CHAT", "NO_MATCH"):
        ss["pending_category"]     = None
        ss["pending_requirements"] = []

    history.add_user_message(query)
    history.add_ai_message(result.response)

    return {
        "category_detected": ss["category"],
        "pending_category":  ss["pending_category"],
        "required_fields":   ss["requirements"],
        "saved_product_id":  saved_product_id,
        "response":          result.response
    }


@router.post("/seller/reset")
async def seller_reset(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id in user_sessions:
        user_sessions[user_id]["session_state"] = {
            "category": None,
            "requirements": [],
            "pending_category": None,
            "pending_requirements": []
        }
        user_sessions[user_id]["chat_history"].clear()
    return {"message": "Seller session reset successfully."}
