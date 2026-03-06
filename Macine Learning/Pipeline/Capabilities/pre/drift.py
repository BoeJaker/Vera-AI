# capabilities/pre/drift.py

import numpy as np
from collections import deque
from capabilities.base import PreLLMCapability

class DriftDetectionCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.window = deque(maxlen=100)

    async def process(self, event, context):
        value = event.get("metric", 0)
        self.window.append(value)

        if len(self.window) < 20:
            context["drift"] = False
            return context

        mean = np.mean(self.window)
        std = np.std(self.window)

        drift = abs(value - mean) > 2 * std

        context["drift"] = drift
        context["drift_stats"] = {
            "mean": float(mean),
            "std": float(std)
        }

        return context