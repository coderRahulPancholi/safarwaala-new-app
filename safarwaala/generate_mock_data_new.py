import frappe
import random
import os
from frappe.utils.file_manager import save_file

IMAGE_PATHS = {
    "Sedan": "/Users/rahulsharma/.gemini/antigravity/brain/3e0a1110-d5b6-4cf1-8e18-e5e41f26ed5c/sedan_car_mock_1764952656935.png",
    "SUV": "/Users/rahulsharma/.gemini/antigravity/brain/3e0a1110-d5b6-4cf1-8e18-e5e41f26ed5c/suv_car_mock_1764952674669.png",
    "Hatchback": "/Users/rahulsharma/.gemini/antigravity/brain/3e0a1110-d5b6-4cf1-8e18-e5e41f26ed5c/hatchback_car_mock_1764952690761.png",
}

REAL_NAMES = [
    "Rahul Sharma", "Amit Patel", "Sneha Gupta", "Vikram Singh", "Priya Desai",
    "Arjun Kumar", "Rohan Mehta", "Anjali Rao", "Suresh Reddy", "Kavita Iyer"
]

VENDOR_NAMES = [
    "Safar Travels", "City Cabs", "Highway Riders", "Royal Fleet", "Urban Drive"
]

CAR_MODALS = [
    {"name": "Toyota Innova Crysta", "capacity": 7, "fuel": "Deisel", "category": "SUV", "transmission": "Manual", "luggage": 4},
    {"name": "Maruti Swift Dzire", "capacity": 5, "fuel": "Petrol", "category": "Sedan", "transmission": "Manual", "luggage": 2},
    {"name": "Hyundai i20", "capacity": 5, "fuel": "Petrol", "category": "Hatchback", "transmission": "Automatic", "luggage": 2},
    {"name": "Mahindra XUV700", "capacity": 7, "fuel": "Deisel", "category": "SUV", "transmission": "Automatic", "luggage": 5},
    {"name": "Honda City", "capacity": 5, "fuel": "Petrol", "category": "Sedan", "transmission": "Automatic", "luggage": 3},
    {"name": "Tata Nexon", "capacity": 5, "fuel": "Deisel", "category": "SUV", "transmission": "Manual", "luggage": 3},
]

def get_random_mobile():
    return '9' + ''.join([str(random.randint(0, 9)) for _ in range(9)])

def create_vendors():
    vendors = []
    print("Creating Vendors...")
    for v_name in VENDOR_NAMES:
        if not frappe.db.exists("Vendors", {"company_name": v_name}):
            doc = frappe.get_doc({
                "doctype": "Vendors",
                "company_name": v_name,
                "mobile": get_random_mobile(),
                "owner_name": random.choice(REAL_NAMES),
                "email": f"{v_name.lower().replace(' ', '')}@example.com"
            })
            doc.insert(ignore_permissions=True)
            print(f"  Created Vendor: {doc.name}")
            vendors.append(doc.name)
        else:
            vendors.append(frappe.get_value("Vendors", {"company_name": v_name}, "name"))
    frappe.db.commit()
    return vendors

def create_car_modals():
    print("Creating Car Modals...")
    created_modals = []
    
    # Reload doctype to ensure fields exist
    frappe.reload_doc("safarwaala", "doctype", "Car Modals")
    
    for m in CAR_MODALS:
        existing_name = frappe.db.get_value("Car Modals", {"modal_name": m["name"]}, "name")
        
        # We want to update even if exists to fill new fields
        if existing_name:
             doc = frappe.get_doc("Car Modals", existing_name)
             doc.category = m["category"]
             doc.transmission = m["transmission"]
             doc.luggage_capacity = m["luggage"]
             doc.night_rate = 250
             doc.min_km_day = 250
             doc.local_hour_rate = 150
             doc.min_local_hour = 8
             doc.min_local_km = 80
             doc.local_km_rate = 12
             doc.save()
             print(f"  Updated Modal: {doc.name}")
             created_modals.append({"name": doc.name, "category": m["category"]})
        else:
            doc = frappe.get_doc({
                "doctype": "Car Modals",
                "modal_name": m["name"],
                "seating_capacity": m["capacity"],
                "fuel_type": m["fuel"],
                "category": m["category"],
                "transmission": m["transmission"],
                "luggage_capacity": m["luggage"],
                "min_km_day": 250,
                "per_km_rate": 15,
                "night_rate": 250,
                "local_hour_rate": 150,
                "min_local_hour": 8,
                "min_local_km": 80,
                "local_km_rate": 12
            })
            doc.insert(ignore_permissions=True)
            print(f"  Created Modal: {doc.name}")
            created_modals.append({"name": doc.name, "category": m["category"]})
    frappe.db.commit()
    return created_modals

def attach_image_to_car(car_doc_name, category):
    image_path = IMAGE_PATHS.get(category)
    if image_path and os.path.exists(image_path):
        filename = os.path.basename(image_path)
        with open(image_path, "rb") as f:
            content = f.read()
            
        # Check if already attached
        if not frappe.db.exists("File", {"attached_to_name": car_doc_name, "file_name": filename}):
            saved_file = save_file(
                filename,
                content,
                "Cars",
                car_doc_name,
                is_private=0
            )
            print(f"  Attached image {filename} to {car_doc_name}")

def create_cars(vendors, modals, count=10):
    print("Creating Cars...")
    for i in range(count):
        modal_info = random.choice(modals)
        vendor = random.choice(vendors)
        license_plate = f"MH{random.randint(10, 48)}{chr(random.randint(65, 90))}{chr(random.randint(65, 90))}{random.randint(1000, 9999)}"
        
        if not frappe.db.exists("Cars", {"license_plate": license_plate}):
            doc = frappe.get_doc({
                "doctype": "Cars",
                "license_plate": license_plate,
                "modal": modal_info["name"],
                "belongs_to_vendor": vendor
            })
            doc.insert(ignore_permissions=True)
            print(f"  Created Car: {doc.name}")
            attach_image_to_car(doc.name, modal_info["category"])
    frappe.db.commit()

def create_drivers(vendors, count=10):
    print("Creating Drivers...")
    for i in range(count):
        name = random.choice(REAL_NAMES) + f" {i+1}" # Append number to ensure uniqueness if picked multiple times
        vendor = random.choice(vendors)
        
        # Check by name approximation or just create
        doc = frappe.get_doc({
            "doctype": "Drivers",
            "name1": name,
            "mobile": get_random_mobile(),
            "owner_vendor": vendor,
            "naming_series": "DRI-.###"
        })
        doc.insert(ignore_permissions=True)
        print(f"  Created Driver: {doc.name}")
    frappe.db.commit()

CITIES = ["Mumbai", "Pune", "Delhi", "Bangalore", "Jaipur", "Udaipur", "Agra", "Ahmedabad", "Surat", "Goa"]

def create_cities():
    print("Creating Cities...")
    
    # Reload doctype to apply autoname change
    frappe.reload_doc("safarwaala", "doctype", "City Master")
    
    # OPTIONAL: Clear old cities to avoid duplicates/confusion if they had hash names
    # frappe.db.delete("City Master") 
    
    created_cities = []
    for city in CITIES:
        # Check if city exists by name (which is now properly the primary key or field)
        if not frappe.db.exists("City Master", city):
            try:
                doc = frappe.get_doc({
                    "doctype": "City Master",
                    "city_name": city
                    # Name will be auto-set to city by autoname rule
                })
                doc.insert(ignore_permissions=True)
                print(f"  Created City: {doc.name}")
                created_cities.append(doc.name)
            except Exception as e:
                print(f"  Error creating {city}: {e}")
        else:
             created_cities.append(city)
    frappe.db.commit()
    return created_cities

def run():
    create_cities()
    vendors = create_vendors()
    modals = create_car_modals()
    create_cars(vendors, modals, count=10)
    create_drivers(vendors, count=10)
    print("Mock data generation complete.")

if __name__ == "__main__":
    run()
