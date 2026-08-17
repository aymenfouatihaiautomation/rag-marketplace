from fastapi import APIRouter, Depends, HTTPException
from database import get_connection
from vector_store import products_db
from routers.auth import get_current_user

router = APIRouter()


@router.get("/products/mine")
def get_my_products(current_user: dict = Depends(get_current_user)):
    """Return all products added by the logged-in user."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, description, category, price, stock, created_at FROM products WHERE user_id = %s ORDER BY created_at DESC",
        (current_user["id"],)
    )
    products = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert decimal/datetime to serializable types
    for p in products:
        p["price"]      = float(p["price"]) if p["price"] is not None else 0.0
        p["created_at"] = str(p["created_at"])

    return {"products": products}


@router.delete("/products/{product_id}")
def delete_product(product_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a product from MySQL and ChromaDB (only if it belongs to the logged-in user)."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Verify ownership
    cursor.execute(
        "SELECT id FROM products WHERE id = %s AND user_id = %s",
        (product_id, current_user["id"])
    )
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found or access denied.")

    # Delete from MySQL
    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()

    # Delete from ChromaDB
    try:
        products_db.delete(ids=[str(product_id)])
    except Exception:
        pass  # If not in ChromaDB, continue silently

    return {"message": f"Product {product_id} deleted successfully."}
