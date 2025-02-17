import requests
from bs4 import BeautifulSoup
import json

url = "https://permits.synchrontms.com/api/v1/getstates"

response = requests.get(url)
data = response.json()

name = "Michigan"
state_details = next((state for state in data["statedetails"] if state["state_name"] == name), None)

if state_details:
    def clean_and_parse(key, value):
        if isinstance(value, str):
            # Handle specific case for "state_info"
            if key == "state_info":
                # Trim everything after "OPERATING TIME"
                if "OPERATING TIME" in value:
                    value = value.split("OPERATING TIME")[0].strip()

            try:
                # Try parsing JSON strings
                parsed = json.loads(value)
                return parsed
            except json.JSONDecodeError:
                soup = BeautifulSoup(value, "html.parser")
                text = soup.get_text(separator=" ").strip()
                return " ".join(text.split())
        return value

    # Clean and parse the state details
    formatted_state_details = {
        key: clean_and_parse(key, value) for key, value in state_details.items()
    }

    # Keys to keep outside of "info"
    main_keys = ["id", "state_name", "state_website", "state_email", "state_phone"]

    # Separate main keys and group the rest under "info"
    main_details = {key: formatted_state_details.pop(key) for key in main_keys if key in formatted_state_details}

    # Define keys to be grouped into "others"
    others_keys = [
        "pricing", "interstate_escort", "route_survey", "police_escort_req", 
        "max_weight_per_axle", "legal_limits", "lane_escort_req", 
        "superload_trigger", "file_autofillerjs", "username", "password", 
        "created_at", "updated_at", "total_permit"
    ]

    # Extract "others" keys and group them into "others" inside "info"
    others = {key: formatted_state_details.pop(key) for key in others_keys if key in formatted_state_details}
    info_details = {"info": formatted_state_details}

    # Add "others" inside "info"
    info_details["info"]["others"] = others

    # Remove the "country" key from "info" if it exists
    if "country" in info_details["info"]:
        del info_details["info"]["country"]

    # Combine main details and info
    final_details = {**main_details, **info_details}

    # Save to a JSON file
    file_name = f"{name}.json"
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(final_details, file, indent=4, ensure_ascii=False)

    print(f"Formatted state details saved to {file_name}.")
else:
    print(f"State with name '{name}' not found.")