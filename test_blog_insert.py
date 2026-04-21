import frappe

def execute():
    try:
        doc = frappe.get_doc({
            "doctype": "Blog",
            "title": "Test Blog From Script",
            "author": "Rahul",
            "short_description": "This is a test description.",
            "content": "<p>Test content here.</p>",
            "status": "Draft",
            "published_on": "2026-04-21"
        })
        doc.insert()
        print("Success! Created Blog:", doc.name)
    except Exception as e:
        print("Error!")
        import traceback
        traceback.print_exc()
