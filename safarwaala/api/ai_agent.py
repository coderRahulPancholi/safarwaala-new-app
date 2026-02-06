import frappe
import json
import openai # OpenRouter uses the standard OpenAI library
from frappe.utils import getdate, nowdate, add_days
from safarwaala.api.booking import create_booking as core_create_booking

# --- 1. Tool Logic (Actual Python Functions) ---

def create_lead(first_name, mobile_no, from_city, to_city, days=1, plan_details=None):
    """Creates a lead/inquiry for a guest user."""
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
            "note": note_content
        })
        doc.insert(ignore_permissions=True)
        return json.dumps({"success": True, "lead_id": doc.name, "message": "Lead created."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def create_booking(pickup_from, start_date, days, vehicle_category, customer_id):
    """Creates a confirmed booking for a logged-in user."""
    try:
        s_date = getdate(start_date)
        e_date = add_days(s_date, int(days))

        booking_data = {
            "customer": customer_id,
            "pickup_location": pickup_from,
            "pickup_datetime": f"{str(s_date)} 10:00:00",
            "return_datetime": f"{str(e_date)} 10:00:00",
            "vehicle_category": vehicle_category
        }
        
        # Call core logic
        res = core_create_booking(booking_type="Outstation Bookings", booking_data=booking_data)
        
        # Handle different return types from core logic
        booking_ref = "Unknown"
        if hasattr(res, 'name'): 
            booking_ref = res.name
        elif isinstance(res, dict):
            booking_ref = res.get('data', {}).get('name') or res.get('name')
            
        return json.dumps({"success": True, "booking_id": booking_ref})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

# --- 2. Tool Schemas ---

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Create a generic inquiry/lead when user is not fully sure or is a guest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "mobile_no": {"type": "string"},
                    "from_city": {"type": "string"},
                    "to_city": {"type": "string"},
                    "days": {"type": "integer"},
                    "plan_details": {"type": "string", "description": "Summary of the itinerary/places discussed"}
                },
                "required": ["first_name", "mobile_no", "from_city", "to_city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": "Create a confirmed booking when user gives explicit permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pickup_from": {"type": "string"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "days": {"type": "integer"},
                    "vehicle_category": {"type": "string", "enum": ["Sedan", "SUV", "Tempo Traveller"]}
                },
                "required": ["pickup_from", "start_date", "days", "vehicle_category"]
            }
        }
    }
]

# --- 3. Main API Endpoint ---

@frappe.whitelist(allow_guest=True)
def chat_agent(message, history=None, customer_id=None):
    try:
        # A. Setup OpenRouter Client
        api_key = frappe.conf.get("OPENROUTER_API_KEY") or "sk-or-v1-key"
        
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        # B. Define Model 
        MODEL_NAME = "google/gemini-2.0-flash-001" 

        # C. Prepare Messages
        if not history: history = []
        if isinstance(history, str): history = json.loads(history)

        system_msg = {
            "role": "system", 
            "content": f"""You are SafarBot (Current Date: {nowdate()}).
            1. When asked to plan a trip:
               - Include famous tourist spots and hidden gems.
               - Separate the plan day-wise.
            2. If User Confirms:
               - GUEST? Call `create_lead`. 
                 * IMPORTANT: You MUST pass the summarized itinerary into the `plan_details` argument.
               - LOGGED IN (ID: {customer_id})? Call `create_booking`.
            3. Always confirm details before booking."""
        }

        messages = [system_msg]
        for msg in history:
            messages.append({"role": msg.get("role"), "content": msg.get("content")})
        
        messages.append({"role": "user", "content": message})

        # D. First Call
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            extra_headers={
                "HTTP-Referer": frappe.utils.get_url(), 
                "X-Title": "Safarwaala App"
            }
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # E. Handle Tool Execution
        if tool_calls:
            # 1. Serialize Tool Calls manually
            tool_calls_payload = []
            for tc in tool_calls:
                tool_calls_payload.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })

            messages.append({
                "role": "assistant",
                "tool_calls": tool_calls_payload, 
                "content": response_message.content
            })

            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                
                tool_res = ""
                if fn_name == "create_booking":
                    if not customer_id:
                        tool_res = json.dumps({"error": "User must login."})
                    else:
                        fn_args['customer_id'] = customer_id
                        tool_res = create_booking(**fn_args)
                elif fn_name == "create_lead":
                    tool_res = create_lead(**fn_args)

                # Add result to history
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": tool_res,
                })

            # F. Final Answer
            final_response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )
            final_content = final_response.choices[0].message.content
        else:
            final_content = response_message.content

        return {
            "role": "assistant",
            "content": final_content
        }

    except Exception as e:
        frappe.log_error(f"OpenRouter Error: {str(e)}")
        return {
            "role": "assistant",
            "content": f"Connection error: {str(e)}"
        }