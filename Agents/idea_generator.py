def IdeaGenerator(agent):
    def generate_ideas(prompt, num_ideas=5):
        """Generate a list of ideas based on the given prompt."""
        idea_prompt = f"Generate {num_ideas} creative ideas for the following prompt:\n\n{prompt}\n\nIdeas:"
        response = agent.fast_llm.invoke(idea_prompt)
        ideas = response.split('\n')
        return [idea.strip('- ').strip() for idea in ideas if idea.strip()]

    return generate_ideas
