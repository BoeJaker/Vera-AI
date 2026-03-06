# routing.py

class ModelRouter:

    def route(self, context):
        if context.get("risk_level") == "HIGH":
            return "llama3:70b"
        if context.get("novel"):
            return "llama3"
        return "mistral"