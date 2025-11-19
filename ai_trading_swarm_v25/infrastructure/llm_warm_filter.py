class LLMWarmFilter:
    def __init__(self, urgency_threshold: float = 0.6):
        self.urgency_threshold = urgency_threshold

    def should_use_big_model(self, features):
        # Later: decide when to route to big vs small models
        return True
