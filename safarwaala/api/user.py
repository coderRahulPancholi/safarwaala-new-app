import frappe
from frappe.auth import LoginManager

@frappe.whitelist(allow_guest=True)
def get_user_profile():
    user = frappe.session.user
    if user == "Guest":
        return {"is_logged_in": False}
    
    user_doc = frappe.get_doc("User", user)
    
    # Fetch linked documents
    vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
    driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")

    return {
        "is_logged_in": True,
        "name": user_doc.name,
        "full_name": user_doc.full_name,
        "first_name": user_doc.first_name,
        "last_name": user_doc.last_name,
        "email": user_doc.email,
        "mobile_no": user_doc.mobile_no,
        "gender": user_doc.gender,
        "birth_date": user_doc.birth_date,
        "user_image": user_doc.user_image,
        "role": user_doc.role_profile_name,
        "vendor_id": vendor,
        "driver_id": driver,
        "customer_details": frappe.db.get_value("Customer", {"linked_user": user}, ["name", "name1", "mobile", "email", "type"], as_dict=True)
    }

@frappe.whitelist(allow_guest=True)
def custom_login(usr, pwd):
    try:
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.throw("Incorrect Email/Username or Password", frappe.AuthenticationError)

    frappe.db.commit()
    user_doc = frappe.get_cached_doc("User", frappe.session.user)
    role = user_doc.role_profile_name or ""

    # Set role cookie directly from backend
    frappe.local.cookie_manager.set_cookie("role", role)

    return {
        "success": True,
        "message": "Logged In Successfully",
        "user": frappe.session.user,
        "role": role
    }

@frappe.whitelist()
def custom_logout():
    frappe.local.login_manager.logout()
    frappe.local.cookie_manager.delete_cookie("role")
    return {"success": True, "message": "Logged out successfully"}
