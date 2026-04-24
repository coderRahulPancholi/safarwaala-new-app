import frappe
import json

@frappe.whitelist(allow_guest=True)
def get_home_screen():
    if not frappe.db.exists("Home Screen Configuration", "Home Screen Configuration"):
        return {"sections": []}
        
    config = frappe.get_doc("Home Screen Configuration", "Home Screen Configuration")
    sections_data = []
    
    for section in config.sections:
        section_data = {
            "section_type": section.section_type,
            "title": section.title,
            "items": []
        }
        
        if section.section_type == "Blogs":
            # Default kwargs
            kwargs = {
                "doctype": "Blog",
                "fields": ["name", "title", "slug", "published_on", "thumbnail", "short_description"],
                "order_by": "published_on desc",
                "limit_page_length": 10
            }
            
            if section.selection_type == "Fixed" and section.fixed_ids:
                ids = [x.strip() for x in section.fixed_ids.split(",") if x.strip()]
                if ids:
                    kwargs["filters"] = {"name": ("in", ids)}
            elif section.selection_type == "Filters" and section.filters_json:
                try:
                    custom_kwargs = json.loads(section.filters_json)
                    if "limit" in custom_kwargs:
                        custom_kwargs["limit_page_length"] = custom_kwargs.pop("limit")
                    kwargs.update(custom_kwargs)
                except Exception:
                    pass
            
            # Ensure Published status if filters is a dict and status isn't specified
            if "filters" not in kwargs:
                kwargs["filters"] = {"status": "Published"}
            elif isinstance(kwargs["filters"], dict) and "status" not in kwargs["filters"]:
                kwargs["filters"]["status"] = "Published"
            
            blogs = frappe.get_all(**kwargs)
            section_data["items"] = blogs
            
        sections_data.append(section_data)
        
    return {"sections": sections_data}
