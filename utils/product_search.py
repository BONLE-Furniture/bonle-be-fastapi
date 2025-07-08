from typing import Optional, List
from math import ceil
from db.database import db
from db.models import sanitize_data
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

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

async def get_search_suggestions_db(query: str) -> List[str]:
    """
    MongoDB에서 검색어를 기반으로 자동완성 제안을 생성합니다.
    
    Args:
        query: 사용자가 입력한 검색어
        
    Returns:
        List[str]: 자동완성 제안 목록 (최대 10개)
    """
    try:
        # 검색어가 너무 짧으면 전체 검색을 시도
        if len(query) < 2:
            pipeline = [
                {
                    "$search": {
                        "index": "product_index",
                        "compound": {
                            "should": [
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "name"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "name_kr"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "brand"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "brand_kr"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "subname"
                                    }
                                },
                                {
                                    "wildcard": {
                                        "query": f"*{query}*",
                                        "path": "subname_kr"
                                    }
                                }
                            ]
                        }
                    }
                },
                {
                    "$project": {
                        "suggestion": {
                            "$concat": [
                                {"$ifNull": ["$name_kr", "$name"]},
                                " ",
                                {"$ifNull": ["$subname_kr", "$subname"]}
                            ]
                        }
                    }
                },
                {
                    "$limit": 10
                }
            ]
        else:
            # 검색어가 2글자 이상이면 autocomplete 사용
            pipeline = [
                {
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
                },
                {
                    "$project": {
                        "suggestion": {
                            "$concat": [
                                {"$ifNull": ["$name_kr", "$name"]},
                                " ",
                                {"$ifNull": ["$subname_kr", "$subname"]}
                            ]
                        }
                    }
                },
                {
                    "$limit": 10
                }
            ]
        
        # 검색 실행
        result = await db["bonre_products"].aggregate(pipeline).to_list(length=10)
        
        # 중복 제거 및 제안 생성
        suggestions = list({
            suggestion["suggestion"].strip() 
            for suggestion in result 
            if suggestion["suggestion"].strip()
        })[:10]
        
        # 여전히 결과가 없으면 빈 문자열 제거
        if not suggestions:
            suggestions = ["검색 결과가 없습니다."]
        
        return suggestions
    except Exception as e:
        logger.error(f"Error in get_search_suggestions_db: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch search suggestions"
        )
