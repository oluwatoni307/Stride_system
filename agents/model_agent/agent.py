# PATH: stride_backend/agents/model_agent/agent.py
# DOMAIN: Defines the Model Agent responsible for building and updating the user behavioural model.

"""
Implements the LangChain agent that analyses accumulated raw store data to construct and update a structured model of user behaviour, capacity, and goal patterns. Delegates execution steps to executor.py and uses prompts from prompts.py. Implemented in Phase 3 (User Modelling). Belongs to the Adaptive Coaching milestone.
"""
