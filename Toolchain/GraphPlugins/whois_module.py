import sys
import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

from Vera.Toolchain.common.common import convert_datetime

class FacebookSearch(PluginBase):
    
    def class_types(self):
        return [
            "name",
            "username",
            "person",
            "email",
            "contact"
        ]
    
    def description(self):
        return "Searches for Facebook profiles based on a given name."
    
    @staticmethod
    def output_class():
        return "metadata"
    
    def execute(self, name, options):
        # URL for Facebook search
        url = f"https://www.facebook.com/search/people/?q={name.replace(' ', '%20')}"
        
        # Headers to mimic a browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Add your Facebook session cookies here (required for logged-in searches)
        cookies = {
            "cookie_name": "cookie_value",  # Replace with your actual Facebook cookies
        }
        
        # Send a GET request to the URL
        response = requests.get(url, headers=headers, cookies=cookies)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all profile links
            profiles = soup.find_all('a', href=True)
            
            # Extract profile URLs
            profile_urls = []
            for profile in profiles:
                if '/profile.php?id=' in profile['href'] or '/user/' in profile['href']:
                    profile_urls.append(f"https://www.facebook.com{profile['href']}")
            
            # Prepare the results
            results = {
                "name": name,
                "profile_urls": profile_urls,
                "timestamp": datetime.now().isoformat()
            }
            
            # Emit the results
            self.socketio.emit("display_results", {"results": json.dumps(results, default=convert_datetime)})
            
            # Save the results to the database
            self.graph_manager.database.set_metadata(name, "facebook_search", "RAW", json.dumps(results, default=convert_datetime))
            self.graph_manager.update_node(name, {"facebook_search_data": results})
            
            return ("display_results", {"results": json.dumps(results, default=convert_datetime)})
        else:
            error_message = f"Failed to retrieve data. Status code: {response.status_code}"
            self.socketio.emit("display_results", {"results": json.dumps({"error": error_message})})
            return ("display_results", {"results": json.dumps({"error": error_message})})

# Example usage
if __name__ == "__main__":
    facebook_search = FacebookSearch()
    results = facebook_search.execute("John Doe", {})
    print(results)