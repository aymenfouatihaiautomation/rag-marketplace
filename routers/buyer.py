from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import PromptTemplate

from embeddings import GROQ_API_KEY
from vector_store import products_db
from routers.auth import get_current_user

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────
class UserMessage(BaseModel):
    message: str

class BuyerResponse(BaseModel):
    response: str
    recommended_product_names: list[str]


# ── LLM ───────────────────────────────────────────────────────────────────────
llm            = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3, groq_api_key=GROQ_API_KEY)
structured_llm = llm.with_structured_output(BuyerResponse)


# ── Prompt ─────────────────────────────────────────────────────────────────────
PROMPT = PromptTemplate(
    input_variables=["retrieved_products", "chat_history", "user_requirements", "user_message"],
    template="""
You are a strict and intelligent e-commerce assistant helping customers find products.

## ACCUMULATED USER REQUIREMENTS
{user_requirements}

## RETRIEVED PRODUCTS FROM DATABASE
{retrieved_products}

## CHAT HISTORY
{chat_history}

## CURRENT USER MESSAGE
{user_message}

## RULES (FOLLOW STRICTLY)

### RULE 1 — FILTER STRICTLY
Read all retrieved products carefully.
Check every product against ALL requirements before recommending it.
If a product fails even ONE requirement -> exclude it completely.
Example: user wants Windows 11 -> MacBook, iPhone, headphones are excluded immediately.
Example: user wants 8GB RAM -> anything without RAM spec or with less RAM is excluded.

### RULE 2 — NEVER SUGGEST IRRELEVANT CATEGORIES
PC/laptop request -> never suggest phones, audio, consoles, accessories.
Match the product category strictly to what the user is asking for.

### RULE 3 — USE FULL REQUIREMENT HISTORY
Always apply ALL accumulated requirements, not just the latest message.
If the user said "PC" two messages ago and now says "suggest me one",
you still know they want a PC with all previously stated specs.

### RULE 4 — BE HONEST ABOUT NO MATCH
If nothing matches all requirements -> say so clearly.
Explain what is missing and ask if they want to relax a requirement.
Never force a bad suggestion.

### RULE 5 — FILL BOTH OUTPUT FIELDS
You MUST always fill both fields:
- response: your natural conversational reply to the user
- recommended_product_names: list of EXACT product names you recommend
  Copy names exactly as they appear in the retrieved products above.
  If you recommend nothing, return an empty list [].
"""
)


# ── Per-user session ───────────────────────────────────────────────────────────
buyer_sessions: dict[int, dict] = {}

def get_session(user_id: int) -> dict:
    if user_id not in buyer_sessions:
        buyer_sessions[user_id] = {
            "chat_history": ChatMessageHistory(),
            "requirements": []
        }
    return buyer_sessions[user_id]


# ── Helpers ────────────────────────────────────────────────────────────────────
def build_search_query(requirements: list[str], current_message: str) -> str:
    return " ".join(requirements + [current_message])

def extract_requirements(message: str, history_str: str) -> list[str]:
    extraction_prompt = f"""
From the following conversation, extract a clean list of ALL technical requirements
the user has stated for the product they want to buy.
Include: product type, OS, RAM, storage, brand preferences, budget, screen size, etc.
Return ONLY a Python list of short requirement strings, nothing else.
Example: ["PC or laptop", "Windows 11", "8GB RAM", "budget under 1500euros"]

Conversation:
{history_str}
Latest message: {message}

Requirements list:
"""
    response = llm.invoke(extraction_prompt)
    text = response.content.strip()
    try:
        import ast
        reqs = ast.literal_eval(text)
        if isinstance(reqs, list):
            return [str(r) for r in reqs]
    except Exception:
        lines = [l.strip().strip('"-') for l in text.replace("[","").replace("]","").split(",") if l.strip()]
        return lines if lines else [message]
    return [message]

def format_retrieved_products(search_results) -> str:
    if not search_results:
        return "No matching products found in database."
    formatted = ""
    for i, doc in enumerate(search_results, 1):
        formatted += f"[Product {i}]\n{doc.page_content}\n\n"
    return formatted.strip()


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/buyer/chat")
async def buyer_chat(user_msg: UserMessage, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    session = get_session(user_id)
    history = session["chat_history"]
    query   = user_msg.message

    history_str = "\n".join(
        f"{'Customer' if m.type == 'human' else 'Assistant'}: {m.content}"
        for m in history.messages
    ) or "No previous conversation."

    # Update accumulated requirements
    session["requirements"] = extract_requirements(query, history_str)
    requirements_str = "\n".join(f"- {r}" for r in session["requirements"]) or "None stated yet."

    # Embed query + search ChromaDB
    search_query   = build_search_query(session["requirements"], query)
    search_results = products_db.similarity_search(search_query, k=8)

    retrieved_products = format_retrieved_products(search_results)

    # LLM reads + filters + returns structured output
    result: BuyerResponse = structured_llm.invoke(PROMPT.format(
        retrieved_products = retrieved_products,
        chat_history       = history_str,
        user_requirements  = requirements_str,
        user_message       = query,
    ))

    history.add_user_message(query)
    history.add_ai_message(result.response)

    # Build card list using only what the LLM explicitly declared
    recommended_lower = [n.lower() for n in result.recommended_product_names]
    matched_products  = [
        {
            "name":     doc.metadata.get("name"),
            "category": doc.metadata.get("category"),
            "price":    doc.metadata.get("price"),
            "stock":    doc.metadata.get("stock"),
        }
        for doc in search_results
        if doc.metadata.get("name", "").lower() in recommended_lower
    ]

    return {
        "products_found":           len(search_results),
        "matched_products":         matched_products,
        "accumulated_requirements": session["requirements"],
        "response":                 result.response
    }


@router.post("/buyer/reset")
async def buyer_reset(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id in buyer_sessions:
        buyer_sessions[user_id]["chat_history"].clear()
        buyer_sessions[user_id]["requirements"] = []
    return {"message": "Buyer session reset successfully."}