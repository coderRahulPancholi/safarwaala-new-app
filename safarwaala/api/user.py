import frappe

@frappe.whitelist()
def get_user_profile():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please login to access this feature", frappe.PermissionError)
    
    user_doc = frappe.get_doc("User", user)
    
    return {
        "name": user_doc.name,
        "full_name": user_doc.full_name,
        "first_name": user_doc.first_name,
        "last_name": user_doc.last_name,
        "email": user_doc.email,
        "mobile_no": user_doc.mobile_no,
        "gender": user_doc.gender,
        "birth_date": user_doc.birth_date,
        "user_image": user_doc.user_image,
        "customer_details": frappe.db.get_value("Customer", {"linked_user": user}, ["name", "name1", "mobile", "email", "type"], as_dict=True)
    }
# path = "safarwaala.api.user.get_user_profile"   
