from typing import Optional
from math import ceil
from db.database import db
from db.models import sanitize_data

async def search_products(
    page: int = 1,
    limit: int = 20,
    category_id: Optional[str] = None,
    query: Optional[str] = None
):
    skip = (page - 1) * limit
    pipeline = []

    # Atlas Search 적용
    if query:
        pipeline.append({
            "$search": {
                "index": "product_index",
                "compound": {
                    "should": [
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "name",
                                "fuzzy": {"maxEdits": 1}
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "name_kr",
                                "fuzzy": {"maxEdits": 1}
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "brand",
                                "fuzzy": {"maxEdits": 1}
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "brand_kr",
                                "fuzzy": {"maxEdits": 1}
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "subname",
                                "fuzzy": {"maxEdits": 1}
                            }
                        },
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "subname_kr",
                                "fuzzy": {"maxEdits": 1}
                            }
                        }
                    ]
                }
            }
        })

    # 업로드된 상품만 필터링
    match_stage = { "upload": True }
    if category_id:
        match_stage["category"] = category_id
    pipeline.append({ "$match": match_stage })

    # 정렬 및 페이징
    pipeline.append({
        "$facet": {
            "documents": [
                { "$sort": { "brand": 1, "name": 1, "subname": 1 } },
                { "$skip": skip },
                { "$limit": limit }
            ],
            "total": [
                { "$count": "count" }
            ]
        }
    })

    result = await db["bonre_products"].aggregate(pipeline).to_list(length=1)
    items = result[0]["documents"]
    total_count = result[0]["total"][0]["count"] if result[0]["total"] else 0

    sanitized_items = sanitize_data(items)
    filtered_items = [
        {
            "_id": str(item["_id"]),
            "name_kr": item.get("name_kr", ""),
            "name": item.get("name", ""),
            "subname": item.get("subname", ""),
            "subname_kr": item.get("subname_kr", ""),
            "brand": item.get("brand_kr", ""),
            "main_image_url": item.get("main_image_url", ""),
            "bookmark_counts": item.get("bookmark_counts", 0),
            "cheapest": item.get("cheapest", [{}])[-1].get("price") if item.get("cheapest") else None,
            "categories": item.get("category", [])
        }
        for item in sanitized_items
    ]

    return {
        "items": filtered_items,
        "item-total-number": total_count,
        "selected-item-number": len(filtered_items),
        "page": page,
        "limit": limit,
        "total_pages": ceil(total_count / limit)
    }
