from typing import Union, Literal
from openai import OpenAI as OpenRouterClient
from pydantic import Field
from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, BaseDynamicContextProvider
from src.config import Config

import instructor
from datetime import datetime


########################
# INPUT/OUTPUT SCHEMAS #
########################
class OrchestratorInputSchema(BaseIOSchema):
    """Input schema for the GLaDOS Agent. Contains the user's message."""

    chat_message: str = Field(..., description="The user's input message to be analyzed and classified.")


class OrchestratorOutputSchema(BaseIOSchema):
    """
    Updated output schema for the GLaDOS Agent.
    It now contains the name of the tool to be used, including a 'No Tool' option.
    """
    tool_name: Literal['Home Assistant Tool', 'SearXNG Tool', 'Vikunja Tool', 'No Tool'] = Field(
        ...,
        description="The name of the tool that should be used to respond to the query. "
                    "Must be one of the following: 'Home Assistant Tool', 'SearXNG Tool', "
                    "or 'Vikunja Tool'. If the query is a simple conversational message and "
                    "does not require any tool to be used, select 'No Tool'."
    )


#####################
# CONTEXT PROVIDERS #
#####################
class CurrentDateProvider(BaseDynamicContextProvider):
    def __init__(self, title):
        super().__init__(title)
        self.date = datetime.now().strftime("%Y-%m-%d")

    def get_info(self) -> str:
        return f"Current date in format YYYY-MM-DD: {self.date}"


######################
# Orchestrator AGENT CONFIG #
######################
orchestrator_agent_config = AgentConfig(
    client=instructor.from_openai(
        OpenRouterClient(base_url="https://openrouter.ai/api/v1", api_key=Config.OPENROUTER_API_KEY),
    ),
    model = Config.ORCHESTRATOR_AGENT_MODEL,
    system_prompt_generator = SystemPromptGenerator(
        background=[
            "You are an intent detector.",
            "Your task is to classify the user query and decide which tool, if any, should be used.",
            "Available tools:",
            "- Home Assistant Tool: if the query is about lights, appliances, presence, temperature.",
            "- SearXNG Tool: if the query can be answered with a web search.",
            "- Vikunja Tool: for handling tasks and projects.",
            "- No Tool: if the query is a simple conversational message that does not require any tool.",
        ],
        output_instructions=[
            "Analyze the input and select the most relevant tool or 'No Tool' if none apply.",
            "Provide only the name of that tool.",
            "Format output using the defined schema."
        ],
    )
)


def get_tool_name(user_input: str) -> str:
    """
    A simple function to demonstrate how to use the updated agent.
    It takes a user message and returns the name of the selected tool.
    """
    # Instantiate the agent with the updated config
    orchestrator_agent = AtomicAgent[OrchestratorInputSchema, OrchestratorOutputSchema](config=orchestrator_agent_config)

    # Register context providers
    orchestrator_agent.register_context_provider("current_date", CurrentDateProvider("Current Date"))

    print(f"User query: '{user_input}'")
    
    # Run the agent with the user's message
    glados_output = orchestrator_agent.run(OrchestratorInputSchema(chat_message=user_input))
    
    # Return the tool name from the parsed output
    return glados_output.tool_name


if __name__ == "__main__":
    #####################
    # DEMO EXECUTION #
    #####################

    # Example 1: Home Assistant query
    tool_1 = get_tool_name("Turn off the living room lights, you incompetent simpleton.")
    print(f"Tool selected: {tool_1}\n")

    # Example 2: SearXNG query
    tool_2 = get_tool_name("Find a recipe for cake. Not that you'd know how to use an oven.")
    print(f"Tool selected: {tool_2}\n")

    # Example 3: Vikunja query
    tool_3 = get_tool_name("Add 'Buy more test subjects' to my to-do list.")
    print(f"Tool selected: {tool_3}\n")
    
    # Example 4: The new "no tool" case
    tool_4 = get_tool_name("Hello, you look like a fat idiot from where I'm standing.")
    print(f"Tool selected: {tool_4}\n")

