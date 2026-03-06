# capabilities/pre/packet_anomaly.py

from sklearn.ensemble import IsolationForest
import numpy as np

class PacketAnomalyCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.model = IsolationForest(contamination=0.05)
        self.model.fit(np.random.rand(200, 6))

    async def process(self, event, context):
        features = np.array(event.get("packet_features", [[0]*6]))
        prediction = self.model.predict(features)[0]

        context["packet_anomaly"] = prediction == -1
        return context