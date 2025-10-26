
def Reviewer(agent):
    # --- Run with feedback ---
    def run_with_feedback(agent, agent_fn, review_fn, query):
        """Run an agent function with feedback loop where the reviewer can accept or reject the output."""
        # First attempt
        response = agent_fn(query)
        
        # Review
        review_result = review_fn(query, response)
        if review_result.startswith("NO"):
            feedback = review_result[4:].strip()
            print(f"\n[ Reviewer ] Feedback: {feedback}")
            # Retry with feedback
            retry_prompt = f"{query}\n\nThe reviewer says: {feedback}\nPlease improve your answer."
            response = agent_fn(retry_prompt)
        
        return response
    
    def review_output(agent, query, response):
        """Simple reviewer that checks if the response is satisfactory."""
        print(f"\n[ Reviewer ] Reviewing response for query: {query}\nResponse: {response}\n")
        print("Is this response satisfactory? (yes/no): ", end="")
        user_input = input().strip().lower()
        if user_input in ['yes', 'y']:
            return "YES"
        else:
            print("Please provide feedback on what to improve: ", end="")
            feedback = input().strip()
            return f"NO: {feedback}"
    
    def agent_reviewer(agent, query, response):
        """Automated reviewer agent that checks the response quality."""
        review_prompt = f"""
        You are a reviewer agent. Evaluate the following response to the query.

        Query: {query}
        Response: {response}

        Criteria:
        - Is the response relevant and accurate?
        - Does it fully address the query?
        - Is the language clear and appropriate?

        If the response is satisfactory, reply with "YES".
        If not, reply with "NO: <specific feedback>".
        """
        review_response = agent.fast_llm.invoke(review_prompt)
        return review_response.strip()
