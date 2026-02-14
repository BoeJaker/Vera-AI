Below is an explanation of each of the agents:

- council
  Asks multiple models the same question at once - only use if expressly asked for

- proactive
  Starts proactive thinking about the current focus - only use if expressly asked for

- simple
  Answers simple questions with quick answers

- toolchain
   executes tools to collect and process information not handled by other agents. If your unsure or its unclear which agent to use for a request, the toolchain will likely be able to fulfill it.

- toolchain-parallel
  For tasks with multiple independent parts that can run simultaneously
  Examples: "Compare X vs Y", "Analyze these 3 files", "Search for A and B"

- toolchain-adaptive
  Intelligent automatic mode selection - good for complex multi-step tasks
  Examples: "Research topic and create report", "Debug and fix this code"

- toolchain-quick
  Fast minimal planning for simple tool sequences
  Examples: "Search for X", "Run this command"

- scheduling-agent 
  Can fulfill scheduling tasks

- reasoning
  Extended reasoning for deep complex answers

- complex
  High-quality output for complex questions

- coding
    Starts a coding specialist model, good for producing quality code