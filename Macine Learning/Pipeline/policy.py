# policy.py

class PolicyEngine:

    def evaluate(self, context):
        if context.get("risk_level") == "HIGH" and not context.get("packet_anomaly"):
            return False
        return True