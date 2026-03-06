# capabilities/pre/anomaly.py

import numpy as np
from sklearn.ensemble import IsolationForest
from capabilities.base import PreLLMCapability

class AnomalyCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.model = IsolationForest(contamination=0.1)
        self.model.fit(np.random.rand(50, 4))

    async def process(self, event, context):
        features = np.array(event.get("features", [[0,0,0,0]]))
        score = self.model.predict(features)[0]

        context["anomaly"] = score == -1
        return context