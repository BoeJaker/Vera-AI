class CapabilityPipeline:

    def __init__(self, pre_caps, post_caps, llm):
        self.pre_caps = pre_caps
        self.post_caps = post_caps
        self.llm = llm

    async def initialize(self, runtime):
        for cap in self.pre_caps + self.post_caps:
            await cap.setup(runtime)

    async def run(self, event):

        context = {"event": event}

        # Pre-LLM
        for cap in self.pre_caps:
            context = await cap.process(event, context)

        # LLM
        model_name = router.route(context)
        llm_output = await self.llm.generate(context, model=model_name)

        context["llm_output"] = llm_output

        # Post-LLM
        for cap in self.post_caps:
            context = await cap.process(llm_output, context)

        return context