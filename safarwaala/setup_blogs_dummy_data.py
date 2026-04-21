import frappe
import random

def get_random_image(idx):
    return f"https://picsum.photos/seed/safarwaala{idx}/1200/630"

def setup():
    frappe.flags.in_test = True
    
    categories = [
        "Travel Tips", "Destinations", "Car Care", "Driver Stories", "Company News", "Offers & Deals"
    ]
    
    cat_docs = {}
    for cat_name in categories:
        if not frappe.db.exists("Category", {"category_name": cat_name}):
            doc = frappe.get_doc({
                "doctype": "Category",
                "category_name": cat_name,
                "is_active": 1
            })
            doc.insert(ignore_permissions=True)
            cat_docs[cat_name] = doc.name
        else:
            cat_docs[cat_name] = frappe.db.get_value("Category", {"category_name": cat_name}, "name")

    for i in range(1, 51):
        title = f"Dummy Blog Post Number {i} on Safarwaala"
        cat_name = random.choice(categories)
        
        # explicitly creating slug to satisfy autoname='field:slug'
        import re
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)

        if not frappe.db.exists("Blog", {"title": title}):
            doc = frappe.get_doc({
                "doctype": "Blog",
                "title": title,
                "slug": slug,
                "author": f"Author {i}",
                "thumbnail": get_random_image(i),
                "short_description": f"This is a comprehensive guide and dummy description for blog {i}. Enjoy reading the best travel advice and tips.",
                "content": f"<h2>Introduction to Blog {i}</h2><p>This is the amazing content for part {i}. We will explore everything there is to know about this topic. Happy traveling!</p><p>We can add more details here.</p>",
                "seo_title": f"Blog {i} | Safarwaala",
                "meta_description": f"Learn more about standard travel tips from Safarwaala blog {i}. We offer the best transport services.",
                "status": "Published",
                "is_featured": 1 if i % 10 == 0 else 0,
                "categories": [
                    {
                        "category": cat_docs[cat_name]
                    }
                ]
            })
            doc.insert(ignore_permissions=True)
        else:
            doc = frappe.get_doc("Blog", {"title": title})
            doc.thumbnail = get_random_image(i)
            doc.save(ignore_permissions=True)

    frappe.db.commit()
    print("50 Dummy Blogs successfully generated.")

if __name__ == "__main__":
    setup()
