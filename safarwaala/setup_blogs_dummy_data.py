import frappe
import random
import re

def get_random_image(idx):
    return f"https://picsum.photos/seed/safarwaalaindia{idx}/1200/630"

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

    # Delete old dummy blogs to keep the database relatively clean
    old_dummies = frappe.get_all("Blog", filters=[["title", "like", "Dummy Blog Post Number%"]])
    for b in old_dummies:
        frappe.delete_doc("Blog", b.name, ignore_permissions=True)

    indian_destinations = [
        "Goa", "Jaipur", "Udaipur", "Agra", "Munnar", "Shimla", "Manali", "Leh", "Darjeeling", "Varanasi",
        "Rishikesh", "Andaman", "Kerala Backwaters", "Amritsar", "Jaisalmer", "Ooty", "Coorg", "Hampi", "Mysore", "Pondicherry",
        "Sikkim", "Spiti Valley", "Auli", "Khajuraho", "Nainital", "Ranthambore", "Kaziranga", "Meghalaya", "Gokarna", "Kutch",
        "Kodaikanal", "Mahabaleshwar", "Lonavala", "Gullmarg", "Dal Lake", "Wayanad", "Varkala", "Kanyakumari", "Madurai", "Rameshwaram",
        "Tirupati", "Puri", "Bhubaneswar", "Kolkata", "Mumbai", "Delhi", "Hyderabad", "Bangalore", "Chennai", "Pune"
    ]

    for i, city in enumerate(indian_destinations, 1):
        title = f"Ultimate Travel Guide to {city}: Top Places to Visit & Hidden Gems"
        cat_name = "Destinations" if random.random() > 0.3 else random.choice(categories) # Bias towards Destinations
        
        # explicitly creating slug to satisfy autoname='field:slug'
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)

        if not frappe.db.exists("Blog", {"title": title}):
            doc = frappe.get_doc({
                "doctype": "Blog",
                "title": title,
                "slug": slug,
                "author": random.choice(["Rahul Sharma", "Priya Menon", "Amit Patel", "Neha Singh"]),
                "thumbnail": get_random_image(i),
                "short_description": f"Planning a trip to {city}? Discover the best places to visit, local cuisine, and travel tips for an unforgettable experience in {city}.",
                "content": f"""
<h2>Why Visit {city}?</h2>
<p>{city} is one of the most culturally rich and visually stunning destinations in India. Whether you are seeking adventure, relaxation, or cultural immersion, {city} has something to offer every traveler. From historical landmarks to vibrant night markets, a trip here promises memories that will last a lifetime.</p>
<blockquote>
"Travel makes one modest. You see what a tiny place you occupy in the world." - A journey to {city} embodies this sentiment perfectly.
</blockquote>
<h3>Top Attractions & Must-do Activities</h3>
<p>Make sure to explore the historical monuments, vibrant local markets, and breathtaking natural scenery. Hiring a rental car from <strong>Safarwaala</strong> can make your journey much more comfortable. Here are the top things you absolutely cannot miss:</p>
<ul>
    <li>Exploring the ancient architecture and local heritage sites.</li>
    <li>Trying out the authentic local street food and delicacies.</li>
    <li>Taking a scenic drive through the outskirts of the city.</li>
    <li>Participating in local cultural festivals or events.</li>
</ul>
<h3>Best Time to Visit</h3>
<p>The ideal time to explore {city} is during the pleasant seasons when the weather is accommodating for sightseeing. Avoid the extreme heat or unpredictable monsoons by planning your trip between October and March. This window offers crisp mornings and beautiful sunsets.</p>
<h3>Getting Around</h3>
<p>To fully experience everything {city} has to offer, having reliable transportation is key. With Safarwaala's premium fleet of cars, you can plan your own itinerary without relying on rigid public transport schedules or expensive private tour guides.</p>
<p>Book your ride today and experience the magic of {city} firsthand!</p>
""",
                "seo_title": f"{city} Travel Guide | Safarwaala",
                "meta_description": f"Explore the ultimate {city} travel guide. Find places to visit, things to do, and travel tips with Safarwaala car rentals.",
                "status": "Published",
                "is_featured": 1 if i <= 3 else 0, # Top 3 are featured
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
            doc.content = f"""
<h2>Why Visit {city}?</h2>
<p>{city} is one of the most culturally rich and visually stunning destinations in India. Whether you are seeking adventure, relaxation, or cultural immersion, {city} has something to offer every traveler. From historical landmarks to vibrant night markets, a trip here promises memories that will last a lifetime.</p>
<blockquote>
"Travel makes one modest. You see what a tiny place you occupy in the world." - A journey to {city} embodies this sentiment perfectly.
</blockquote>
<h3>Top Attractions & Must-do Activities</h3>
<p>Make sure to explore the historical monuments, vibrant local markets, and breathtaking natural scenery. Hiring a rental car from <strong>Safarwaala</strong> can make your journey much more comfortable. Here are the top things you absolutely cannot miss:</p>
<ul>
    <li>Exploring the ancient architecture and local heritage sites.</li>
    <li>Trying out the authentic local street food and delicacies.</li>
    <li>Taking a scenic drive through the outskirts of the city.</li>
    <li>Participating in local cultural festivals or events.</li>
</ul>
<h3>Best Time to Visit</h3>
<p>The ideal time to explore {city} is during the pleasant seasons when the weather is accommodating for sightseeing. Avoid the extreme heat or unpredictable monsoons by planning your trip between October and March. This window offers crisp mornings and beautiful sunsets.</p>
<h3>Getting Around</h3>
<p>To fully experience everything {city} has to offer, having reliable transportation is key. With Safarwaala's premium fleet of cars, you can plan your own itinerary without relying on rigid public transport schedules or expensive private tour guides.</p>
<p>Book your ride today and experience the magic of {city} firsthand!</p>
"""
            doc.author = random.choice(["Rahul Sharma", "Priya Menon", "Amit Patel", "Neha Singh"])
            doc.short_description = f"Planning a trip to {city}? Discover the best places to visit, local cuisine, and travel tips for an unforgettable experience in {city}."
            doc.seo_title = f"{city} Travel Guide | Safarwaala"
            doc.meta_description = f"Explore the ultimate {city} travel guide. Find places to visit, things to do, and travel tips with Safarwaala car rentals."
            doc.save(ignore_permissions=True)

    frappe.db.commit()
    print("50 Indian City Blogs successfully generated.")

if __name__ == "__main__":
    setup()
