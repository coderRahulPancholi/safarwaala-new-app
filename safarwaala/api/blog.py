"""
Blog API endpoints for Safarwaala frontend (safarwaala_user).
"""

import frappe


@frappe.whitelist(allow_guest=True)
def get_blogs(page=1, limit=9, category=None, featured=None):
    """
    Returns paginated list of published blogs.
    Used by /blogs listing page.
    """
    page = int(page)
    limit = int(limit)
    offset = (page - 1) * limit

    filters = {"status": "Published"}
    if category:
        # Get blogs that have this category in the child table
        filters["name"] = ["in", frappe.get_all(
            "Category Item", 
            filters={"category": category}, 
            pluck="parent"
        )]
    if featured is not None:
        filters["is_featured"] = 1 if str(featured) in ("1", "true") else 0

    blogs = frappe.get_list(
        "Blog",
        filters=filters,
        fields=[
            "name",
            "title",
            "slug",
            "published_on",
            "author",
            "thumbnail",
            "short_description",
            "reading_time",
            "is_featured",
            "tags",
        ],
        order_by="published_on desc",
        start=offset,
        page_length=limit,
    )

    # Fetch categories for the listed blogs
    if blogs:
        blog_names = [b.name for b in blogs]
        categories_map = {}
        for cat in frappe.get_all("Category Item", filters={"parent": ["in", blog_names]}, fields=["parent", "category"]):
            categories_map.setdefault(cat.parent, []).append(cat.category)
        
        for b in blogs:
            b.categories = categories_map.get(b.name, [])
            b.category = b.categories[0] if b.categories else "Uncategorized"  # Fallback for frontend

    total = frappe.db.count("Blog", filters=filters)

    return {
        "data": blogs,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@frappe.whitelist(allow_guest=True)
def get_blog(slug):
    """
    Returns full blog post data including all SEO fields.
    Used by /blogs/[slug] detail page.
    """
    blog = frappe.db.get_value(
        "Blog",
        {"slug": slug, "status": "Published"},
        [
            "name",
            "title",
            "slug",
            "status",
            "published_on",
            "author",
            "thumbnail",
            "short_description",
            "content",
            "tags",
            "reading_time",
            "is_featured",
            "seo_title",
            "meta_description",
            "canonical_url",
            "focus_keyword",
            "og_title",
            "og_description",
            "og_image",
            "og_type",
            "twitter_title",
            "twitter_description",
            "twitter_image",
            "twitter_card_type",
            "schema_type",
            "schema_json",
        ],
        as_dict=True,
    )

    if not blog:
        frappe.throw("Blog not found", frappe.DoesNotExistError)

    categories = frappe.get_all("Category Item", filters={"parent": blog.name}, pluck="category")
    blog.categories = categories
    blog.category = categories[0] if categories else "Uncategorized"

    return {"data": blog}


@frappe.whitelist(allow_guest=True)
def get_related_blogs(slug, limit=3):
    """
    Returns related blog posts (same category, excluding current).
    """
    current = frappe.db.get_value("Blog", {"slug": slug}, "name")
    if not current:
        return {"data": []}

    categories = frappe.get_all("Category Item", filters={"parent": current}, pluck="category")
    if not categories:
        return {"data": []}

    filters = {
        "status": "Published",
        "name": ["!=", current],
    }

    # Find blogs that share at least one category
    related_names = frappe.get_all("Category Item", filters={"category": ["in", categories], "parent": ["!=", current]}, pluck="parent")
    
    if not related_names:
        return {"data": []}
        
    filters["name"] = ["in", related_names]

    blogs = frappe.get_list(
        "Blog",
        filters=filters,
        fields=["name", "title", "slug", "thumbnail", "short_description", "published_on", "reading_time", "author"],
        order_by="published_on desc",
        page_length=int(limit),
    )
    
    if blogs:
        blog_names = [b.name for b in blogs]
        categories_map = {}
        for cat in frappe.get_all("Category Item", filters={"parent": ["in", blog_names]}, fields=["parent", "category"]):
            categories_map.setdefault(cat.parent, []).append(cat.category)
        
        for b in blogs:
            b.categories = categories_map.get(b.name, [])
            b.category = b.categories[0] if b.categories else "Uncategorized"

    return {"data": blogs}


@frappe.whitelist(allow_guest=True)
def get_all_slugs():
    """
    Returns all published blog slugs.
    Used by Next.js generateStaticParams for ISR pre-generation.
    """
    slugs = frappe.get_all(
        "Blog",
        filters={"status": "Published"},
        pluck="slug",
    )
    return {"slugs": slugs}

