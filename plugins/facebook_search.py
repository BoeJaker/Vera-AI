""""
https://www.facebook.com/search/people/?q=name

a.href a.inner
"""
from fuzzywuzzy import fuzz, process

# Assuming you have a list of Facebook profiles or a data source
facebook_profiles = [
    "facebook.com/johndoe",
    "facebook.com/janedoe",
    "facebook.com/example",
    # Add more profiles as needed
]

def lookup_facebook_profile(query):
    # Perform fuzzy matching using fuzzywuzzy library (install it with pip install fuzzywuzzy)
    matches = process.extract(query, facebook_profiles, scorer=fuzz.partial_ratio, limit=5)
    
    # Extract the best match
    best_match, score = matches[0]
    
    # Check if the score meets a certain threshold to consider it a valid match
    if score >= 80:  # Adjust score threshold based on your needs
        return best_match
    else:
        return "No matching profile found."

# Example usage
query = "john doe"
result = lookup_facebook_profile(query)
print(f"Best match for '{query}': {result}")
