import frappe

def setup_dummy_data():
    frappe.flags.in_test = True
    
    categories = [
        {"category_name": "Travel Tips", "description": "Expert advice.", "color": "#FC632C"},
        {"category_name": "Destinations", "description": "Explore places.", "color": "#3B82F6"},
        {"category_name": "Car Care", "description": "Vehicle tips.", "color": "#10B981"},
        {"category_name": "Driver Stories", "description": "First-hand experiences.", "color": "#8B5CF6"},
        {"category_name": "Company News", "description": "Updates.", "color": "#F59E0B"},
        {"category_name": "Offers & Deals", "description": "Promotions.", "color": "#EF4444"},
    ]
    
    cat_docs = {}
    for cat in categories:
        if not frappe.db.exists("Category", {"category_name": cat["category_name"]}):
            doc = frappe.get_doc({
                "doctype": "Category",
                **cat,
                "is_active": 1
            })
            doc.insert(ignore_permissions=True)
            cat_docs[cat["category_name"]] = doc.name
        else:
            cat_docs[cat["category_name"]] = frappe.db.get_value("Category", {"category_name": cat["category_name"]}, "name")

    blogs = [
        {
            "title": "Top 10 Road Trip Routes in India You Must Try",
            "author": "Rahul Sharma",
            "category_name": "Destinations",
            "thumbnail": "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1200&h=630&fit=crop&q=80",
            "short_description": "Discover India's most breathtaking road trip routes.",
            "content": "<h2>1. Mumbai to Goa</h2><p>One of the most iconic drives...</p>",
            "seo_title": "Top 10 Road Trip Routes | Safarwaala",
            "meta_description": "Discover India's must-do road trips.",
            "status": "Published",
            "is_featured": 1
        },
        {
            "title": "How to Pack Smart for a Long Trip",
            "author": "Priya Menon",
            "category_name": "Travel Tips",
            "thumbnail": "https://images.unsplash.com/photo-1553913861-c0fddf2619ee?w=1200&h=630&fit=crop&q=80",
            "short_description": "Smart packing can make or break a long road trip.",
            "content": "<h2>Less is More</h2><p>Focus on versatile clothing...</p>",
            "seo_title": "Smart Packing Tips | Safarwaala",
            "meta_description": "Pack smarter, travel better.",
            "status": "Published",
            "is_featured": 0
        }
    ]

    for blog in blogs:
        if not frappe.db.exists("Blog", {"title": blog["title"]}):
            doc = frappe.get_doc({
                "doctype": "Blog",
                "title": blog.get("title"),
                "author": blog.get("author"),
                "thumbnail": blog.get("thumbnail"),
                "short_description": blog.get("short_description"),
                "content": blog.get("content"),
                "seo_title": blog.get("seo_title"),
                "meta_description": blog.get("meta_description"),
                "status": blog.get("status"),
                "is_featured": blog.get("is_featured"),
                "categories": [
                    {
                        "category": cat_docs[blog["category_name"]]
                    }
                ]
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()
    print("Dummy data successfully generated.")

if __name__ == "__main__":
    setup_dummy_data()
