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

def find_best_match_car(user_query, passengers=1):
    """
    Tries to find a suitable Car Modal based on user's text query.
    """
    try:
        pax = int(passengers) if passengers else 1
        q = user_query.lower().strip() if user_query else ""

        # A. Category Search (Generic)
        if q in ["sedan", "small car", "cab", "taxi"]:
            return frappe.db.get_value("Car Modals", 
                {"category": "Sedan", "seating_capacity": [">=", pax]}, "name", order_by="per_km_rate asc")
        
        if q in ["suv", "muv", "big car", "large car", "ertiga", "innova"]:
            # Prefer Innova for SUV generally if available
            return frappe.db.get_value("Car Modals", 
                {"category": ["in", ["SUV", "MUV"]], "seating_capacity": [">=", pax]}, "name", order_by="per_km_rate asc")

        # B. Fuzzy/Like Search on Name
        car = frappe.db.get_value("Car Modals", 
            {"name": ["like", f"%{user_query}%"], "seating_capacity": [">=", pax]}, 
            "name"
        )
        if car: return car
        
        return None
    except:
        return None

# --- 2. Tool Logic (Actual Python Functions) ---

def estimate_trip_cost(days, passengers=1, from_city=None, to_city=None):
    """Calculates approximate Round Trip cost for Sedan and SUV."""
    try:
        days = int(days) if days else 1
        min_km_day = 300 
        total_min_km = min_km_day * days
        
        # 1. Sedan Estimates
        sedan_rate = 11 # Fallback
        sedan = frappe.db.get_value("Car Modals", {"category": "Sedan"}, ["per_km_rate", "min_km_day"], as_dict=True)
        if sedan:
            sedan_rate = sedan.per_km_rate
            if sedan.min_km_day: min_km_day = sedan.min_km_day
            total_min_km = min_km_day * days
            
        sedan_cost = total_min_km * sedan_rate
        
        # 2. SUV Estimates
        suv_rate = 16 # Fallback
        suv = frappe.db.get_value("Car Modals", {"category": ["in", ["SUV", "MUV"]]}, ["per_km_rate"], as_dict=True)
        if not suv:
             suv = frappe.db.get_value("Car Modals", {"naming_series": ["like", "%Innova%"]}, ["per_km_rate"], as_dict=True)
        if suv:
            suv_rate = suv.per_km_rate
            
        suv_cost = total_min_km * suv_rate
        
        trip_type_lbl = "Round Trip"
        
        response = {
            "success": True,
            "details": {
                "days": days,
                "type": trip_type_lbl,
                "min_km_considered": total_min_km,
                "sedan": {
                    "rate": sedan_rate,
                    "estimated_total": sedan_cost,
                    "description": "Ideal for 1-4 Pax"
                },
                "suv": {
                    "rate": suv_rate,
                    "estimated_total": suv_cost,
                    "description": "Ideal for 5-7 Pax"
                }
            },
            "message": (
                f"**🏷️ Estimated {trip_type_lbl} Cost for {days} Days**\n"
                f"_(Min {total_min_km} km chargeable)_\n\n"
                f"🚗 **Sedan**: ~₹{sedan_cost:,} *(max 4 Pax)*\n"
                f"🚙 **SUV**: ~₹{suv_cost:,} *(max 7 Pax)*\n\n"
                f"ℹ️ *Excludes tolls, parking & driver allowance. Final price on actuals.*"
            )
        }
        
        return json.dumps(response)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def create_lead_internal(name, mobile, from_city, to_city, note=""):
    """Internal helper to create a lead safely."""
    try:
        doc = frappe.get_doc({
            "doctype": "Lead",
            "first_name": name,
            "mobile_no": mobile,
            "status": "Open",
            "source": "Website",
            "from_city": from_city,
            "to_city": to_city,
            "booking_type": "OutStation Booking",
            "trip_type": "RoundTrip", 
            "note": note
        })
        doc.insert(ignore_permissions=True)
        return doc.name
    except:
        return None

def create_lead(first_name, mobile_no, from_city, to_city, days=1, plan_details=None):
    """Creates a lead/inquiry via Tool."""
    try:
        note_content = f"Planning for {days} days via AI."
        if plan_details:
            note_content += f"\n\nAI Generated Plan:\n{plan_details}"

        lead_id = create_lead_internal(first_name, mobile_no, from_city, to_city, note_content)
        
        if lead_id:
             return json.dumps({"success": True, "lead_id": lead_id, "message": f"✅ Inquiry Created! Lead ID: {lead_id}"})
        else:
             return json.dumps({"success": False, "error": "Could not create lead."})
            
    except Exception as e:
        frappe.log_error(f"Lead Creation Error: {str(e)}", "AI Agent Error")
        return json.dumps({"success": False, "error": str(e)})

def create_booking(pickup_from, to_city, passengers, customer_id, days=1, start_date=None, user_car_choice=None, plan_summary=None):
    """Creates a confirmed Bookings Master with optional plan details."""
    try:
        if not start_date:
            start_date = nowdate()
            
        s_date = getdate(start_date)
        e_date = add_days(s_date, int(days)) if days else s_date

        # Resolve Car Modal
        car_modal = None
        if user_car_choice:
            car_modal = find_best_match_car(user_car_choice, passengers)
            if not car_modal:
                 return json.dumps({
                     "success": False, 
                     "error": f"⚠️ Could not find a car matching '{user_car_choice}'. Please ask the user to choose: Sedan, SUV, or Innova."
                 })
        else:
             return json.dumps({
                 "success": False, 
                 "error": "⚠️ Car Model not specified. Please ask user: 'Which car would you like? (Sedan/SUV/Innova)'"
             })

        # Try Creating Booking
        doc = frappe.get_doc({
            "doctype": "Bookings Master",
            "booking_type": "Outstation", 
            "customer": customer_id,
            "car_modal": car_modal, 
            "pickup_location": pickup_from,
            "drop_location": to_city,
            "pickup_datetime": f"{str(s_date)} 10:00:00",
            "return_datetime": f"{str(e_date)} 22:00:00",
            "booking_status": "Pending",
            "trip_type": "RoundTrip",
            "trip_plan_text": plan_summary if plan_summary else "" # New Field
        })
        
        doc.insert(ignore_permissions=True)
        frappe.db.commit() 
        
        if frappe.db.exists("Bookings Master", doc.name):
            return json.dumps({
                "success": True, 
                "booking_id": doc.name, 
                "car_assigned": car_modal,
                "message": f"✅ **Booking Confirmed!**\n🆔 ID: `{doc.name}`\n🚗 Car: {car_modal}\n📅 Date: {s_date}"
            })
        else:
            raise Exception("Persistence failed")

    except Exception as e:
        # --- SMART FALLBACK ---
        try:
            cust = frappe.get_doc("Customer", customer_id)
            note = f"Booking Failed Fallback. Car: {user_car_choice}, Pax: {passengers}."
            if plan_summary:
                note += f"\n\nPlanned Itinerary:\n{plan_summary}"
                
            lead_id = create_lead_internal(cust.name1, cust.mobile, pickup_from, to_city, note)
            return json.dumps({
                "success": True, 
                "fallback": True,
                "message": f"⚠️ I couldn't confirm the instant booking due to a system glitch, BUT I have created a **Priority Inquiry** for you (Lead `{lead_id}`).\n📞 Our support team will call you shortly to confirm."
            })
        except:
             frappe.log_error(f"Booking & Fallback Error: {str(e)}")
             return json.dumps({"success": False, "error": f"System Error: {str(e)}"})

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
                    "start_date": {"type": "string"},
                    "passengers": {"type": "integer"},
                    "days": {"type": "integer"},
                    "user_car_choice": {"type": "string", "description": "Mandatory. The car model/category (Sedan, SUV, Innova)."},
                    "plan_summary": {"type": "string", "description": "If a trip plan was generated in proper context, summarize it here for reference."}
                },
                "required": ["pickup_from", "to_city", "passengers", "user_car_choice"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Create a general inquiry/lead for GUESTS. DO NOT USE THIS FOR PLANNING TRIPS. Use this ONLY if user explicitly wants to be contacted.",
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
            "name": "estimate_trip_cost",
            "description": "Get estimated Round Trip cost for a trip based on days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days"},
                    "passengers": {"type": "integer"},
                    "from_city": {"type": "string"},
                    "to_city": {"type": "string"}
                },
                "required": ["days"]
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
        # MODEL_NAME = "google/gemini-2.0-flash-001" 
        # MODEL_NAME = "arcee-ai/trinity-large-preview:free" 
        # MODEL_NAME = "openrouter/pony-alpha" 
        MODEL_NAME = "openrouter/aurora-alpha" 

        # B. Get Customer Context
        customer_ctx = ""
        user_name = "traveler"
        if customer_id:
            cust_details = get_customer_details(customer_id)
            if cust_details:
                user_name = cust_details.get('name') or "traveler"
                customer_ctx = f"Logged-in Customer: {user_name} (Mobile: {cust_details.get('mobile')}). ID: {customer_id}."
            else:
                customer_ctx = f"Logged-in Customer ID: {customer_id}."
        
        # C. System Prompt (Persona & Instructions)
        system_msg = {
            "role": "system", 
            "content": f"""You are **SafarBot**, an intelligent, polite, and culturally aware travel assistant for **Safarwaala** in India. Date: {nowdate()}.
            
            **User Context**:
            {customer_ctx}
            
            **Persona**:
            - **Tone**: Warm, helpful, professional, and Indian-friendly (e.g., use "Namaste", "Ji" occasionally for politeness if fits).
            - **Greeting**: Always address the user by Name ({user_name}) if known.
            - **Style**: Use rich Markdown (**Bold** for emphasis, lists for clarity, Emojis 🚗✨ for engagement).
            
            **Capabilities & Rules**:
            
            1. **Booking (Logged-in Only)**:
               - **Mandatory**: User MUST specify a Car (Sedan, SUV, Innova).
               - If missing: Ask politely: *"Which vehicle would you prefer, {user_name}? We have Sedan, SUV, and Innova."*
               - **Saving Plan**: If you just generated a Trip Plan (itinerary), you MUST pass a summary of it to the `plan_summary` argument in `create_booking`.
               - Once specified: Call `create_booking`. 
               - If tool returns a **Fallback** message (Lead created), apologize and inform the user warmly.
               
            2. **Booking (Guest ONLY)**:
               - Ask Name & Mobile -> Call `create_lead`.
               - **WARNING**: Do NOT call `create_lead` if user just asks for a "Plan" or "Itinerary". ONLY call if they want to BOOK or INQUIRE.
               
            3. **Cost Estimates**:
               - If asked "How much?"/ "Price?", use `estimate_trip_cost`. 
               - **Always** assume Round Trip logic.
               
            4. **Trip Planning (Strict Text Only)**:
               - If user asks for a plan ("Plan a trip to X", "Itinerary for Y"):
               - **DO NOT CALL ANY TOOLS.**
               - **DO NOT** call `create_lead`.
               - **JUST WRITE THE TEXT PLAN.**
               - **Format**: Structured Markdown Plan.
                 **🗺️ Trip to [Location]**
                 ...
                 **Summary**
                 - 🚗 Recommended: [Sedan/SUV]
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
                elif fn_name == "estimate_trip_cost":
                    tool_res = estimate_trip_cost(**fn_args)

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