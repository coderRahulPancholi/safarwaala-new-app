import frappe
import json
import openai # OpenRouter uses the standard OpenAI library
from frappe.utils import getdate, nowdate, add_days

# --- 1. Helper Functions ---
def get_customer_details(customer_id):
    """Fetches Name and Mobile for a logged-in customer."""
    try:
        cust = frappe.get_doc("Customer", customer_id)
        return {
            "name": cust.name1,
            "mobile": cust.mobile
        }
    except:
        return None

def get_auto_assigned_car_modal(passengers):
    """Finds a suitable Car Modal based on passenger count."""
    try:
        pax = int(passengers)
        # Search for any car modal with enough capacity
        # We sort by seating_capacity ASC to get the most economical option first (e.g., 4 seater for 3 ppl instead of 7 seater)
        car_modal = frappe.db.get_value("Car Modals", 
            {"seating_capacity": [">=", pax]}, 
            "name", 
            order_by="seating_capacity asc" 
        )
        return car_modal
    except:
        return None

# --- 2. Tool Logic (Actual Python Functions) ---

def create_lead(first_name, mobile_no, from_city, to_city, days=1, plan_details=None):
    """Creates a lead/inquiry for a guest user via Website source."""
    try:
        note_content = f"Planning for {days} days via AI."
        if plan_details:
            note_content += f"\n\nAI Generated Plan:\n{plan_details}"

        doc = frappe.get_doc({
            "doctype": "Lead",
            "first_name": first_name,
            "mobile_no": mobile_no,
            "status": "Open",
            "source": "Website",
            "from_city": from_city,
            "to_city": to_city,
            "pickup_location": from_city, 
            "drop_location": to_city, 
            "booking_type": "OutStation Booking",
            "trip_type": "RoundTrip", 
            "note": note_content
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit() 
        
        return json.dumps({"success": True, "lead_id": doc.name, "message": "Lead created."})
            
    except Exception as e:
        frappe.log_error(f"Lead Creation Error: {str(e)}", "AI Agent Error")
        return json.dumps({"success": False, "error": str(e)})

def create_booking(pickup_from, to_city, passengers, customer_id, days=1, start_date=None):
    """Creates a confirmed Bookings Master entry directly."""
    try:
        if not start_date:
            start_date = nowdate()
            
        s_date = getdate(start_date)
        e_date = add_days(s_date, int(days)) if days else s_date

        # Auto-select Car Modal
        car_modal = get_auto_assigned_car_modal(passengers)
        if not car_modal:
             return json.dumps({"success": False, "error": f"No suitable car found for {passengers} passengers."})

        # Create Bookings Master Directly
        # We bypass the specific 'OutStation Bookings' doc and go straight to Master as requested
        doc = frappe.get_doc({
            "doctype": "Bookings Master",
            "booking_type": "Outstation", # Default to Outstation based on context
            "customer": customer_id,
            "car_modal": car_modal, 
            "pickup_location": pickup_from,
            "drop_location": to_city,
            "from_city": pickup_from, 
            "to_city": to_city,
            "pickup_datetime": f"{str(s_date)} 10:00:00",
            "return_datetime": f"{str(e_date)} 22:00:00",
            "booking_status": "Confirmed"
        })
        
        doc.insert(ignore_permissions=True)
        frappe.db.commit() 
        
        # Verify
        if frappe.db.exists("Bookings Master", doc.name):
            return json.dumps({"success": True, "booking_id": doc.name, "car_assigned": car_modal})
        else:
            return json.dumps({"success": False, "error": "Booking persistence failed."})

    except Exception as e:
        frappe.log_error(f"Booking Creation Error: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})

# --- 3. Tool Schemas ---

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": "Create a confirmed booking immediately (Only for logged-in users).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pickup_from": {"type": "string"},
                    "to_city": {"type": "string"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD. Optional. Default to Today if not mentioned."},
                    "passengers": {"type": "integer"},
                    "days": {"type": "integer", "description": "Duration. Default 1 if not mentioned."}
                },
                "required": ["pickup_from", "to_city", "passengers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Create a generic inquiry/lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "mobile_no": {"type": "string"},
                    "from_city": {"type": "string"},
                    "to_city": {"type": "string"},
                    "days": {"type": "integer"},
                    "plan_details": {"type": "string"}
                },
                "required": ["first_name", "mobile_no", "from_city", "to_city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_itinerary",
            "description": "Present a structured day-wise trip plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "estimated_cost": {"type": "integer"},
                    "required_vehicle": {"type": "string"},
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "string"},
                                "activity": {"type": "string"},
                                "stay": {"type": "string"},
                                "attractions": {"type": "array", "items": {"type": "string"}}
                            },
                        }
                    }
                },
                "required": ["title", "segments"]
            }
        }
    }
]

# --- 4. Main API Endpoint ---

@frappe.whitelist(allow_guest=True)
def chat_agent(message, history=None, customer_id=None):
    try:
        # A. Setup Client
        api_key = frappe.conf.get("OPENROUTER_API_KEY") or "sk-or-v1-key"
        client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        MODEL_NAME = "google/gemini-2.0-flash-001" 

        # B. Get Customer Context
        customer_ctx = ""
        if customer_id:
            cust_details = get_customer_details(customer_id)
            if cust_details:
                customer_ctx = f"Logged-in Customer: {cust_details.get('name')} (Mobile: {cust_details.get('mobile')}). ID: {customer_id}."
            else:
                customer_ctx = f"Logged-in Customer ID: {customer_id} (Details not found)."
        
        # C. System Prompt
        system_msg = {
            "role": "system", 
            "content": f"""You are SafarBot (Date: {nowdate()}).
            
            **Authentication Context**:
            {customer_ctx}
            
            **Rules**:
            1. **Concise**: Answers must be short (max 2 sentences).
            2. **Direct Booking**:
               - If user says something like "Book for 3 people to Goa from Jaipur":
                 - IF {customer_id}: Call `create_booking` immediately. Do NOT ask for car type. Do NOT ask for date (assume today).
                 - IF Guest: Ask Name/Mobile -> `create_lead`.
            3. **Visuals**:
               - Use `suggest_itinerary` for planning requests only.
            """
        }

        # D. Build Message Chain
        if not history: history = []
        if isinstance(history, str): history = json.loads(history)
        
        messages = [system_msg]
        for msg in history:
            messages.append({"role": msg.get("role"), "content": msg.get("content")})
        messages.append({"role": "user", "content": message})

        # E. Main Loop
        response = client.chat.completions.create(
            model=MODEL_NAME, messages=messages, 
            tools=TOOLS_SCHEMA, tool_choice="auto",
            extra_headers={"HTTP-Referer": frappe.utils.get_url(), "X-Title": "Safarwaala"}
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        trip_plan_data = None 

        if tool_calls:
            # Serialize
            tool_calls_payload = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in tool_calls]
            messages.append({"role": "assistant", "tool_calls": tool_calls_payload, "content": response_message.content})

            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                tool_res = ""

                if fn_name == "create_booking":
                    if not customer_id: tool_res = json.dumps({"error": "Login required."})
                    else:
                        fn_args['customer_id'] = customer_id
                        tool_res = create_booking(**fn_args)
                elif fn_name == "create_lead":
                    tool_res = create_lead(**fn_args)
                elif fn_name == "suggest_itinerary":
                    trip_plan_data = fn_args
                    tool_res = json.dumps({"success": True})

                messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": fn_name, "content": tool_res})

            final_response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
            final_content = final_response.choices[0].message.content
        else:
            final_content = response_message.content

        return {
            "role": "assistant",
            "content": final_content,
            "tripPlan": trip_plan_data 
        }

    except Exception as e:
        frappe.log_error(f"AI Error: {str(e)}")
        return {"role": "assistant", "content": f"System Error: {str(e)}"}