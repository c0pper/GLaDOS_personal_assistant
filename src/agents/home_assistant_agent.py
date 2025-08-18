from enum import Enum
from typing import List, Literal, Optional
from openai import OpenAI as OpenRouterClient
from pydantic import Field
from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, BaseDynamicContextProvider, ChatHistory
from src.config import Config
import instructor
import requests
from src.logger import logger


##########################
# CENTRAL INTENTS CONFIG #
##########################
class IntentName(str, Enum):
    GetTemperature = "GetTemperature"
    GetStateMother = "GetStateMother"
    GetStateFather = "GetStateFather"
    TurnOnCeilingLights = "TurnOnCeilingLights"
    TurnOffCeilingLights = "TurnOffCeilingLights"
    TurnOnMoodLights = "TurnOnMoodLights"
    TurnOffMoodLights = "TurnOffMoodLights"
    TurnOnAllBedroomLights = "TurnOnAllBedroomLights"
    TurnOffAllBedroomLights = "TurnOffAllBedroomLights"
    TurnOnKeyboardStrip = "TurnOnKeyboardStrip"
    TurnOffKeyboardStrip = "TurnOffKeyboardStrip"


########################
# INPUT/OUTPUT SCHEMAS #
########################
class HomeAssistantInputSchema(BaseIOSchema):
    """Input schema for Home Assistant Agent."""
    user_query: str = Field(..., description="The user's home automation query to be processed.")


class HomeAssistantOutputSchema(BaseIOSchema):
    """Output schema for Home Assistant Agent."""
    intent_name: IntentName = Field(
        ..., description="The intent name that matches the user query."
    )


#####################
# CONTEXT PROVIDERS #
#####################
class AvailableIntentsProvider(BaseDynamicContextProvider):
    def __init__(self, title):
        super().__init__(title)
        self.intents = [intent.value for intent in IntentName]

    def get_info(self) -> str:
        return "Available Intents:\n" + "\n".join(self.intents)


######################
# HOME AGENT CONFIG #
######################
home_assistant_agent_config = AgentConfig(
    client=instructor.from_openai(
        OpenRouterClient(base_url="https://openrouter.ai/api/v1", api_key=Config.OPENROUTER_API_KEY),
    ),
    model=Config.HOME_ASSISTANT_AGENT_MODEL,
    history=ChatHistory(max_messages=5),
    system_prompt_generator=SystemPromptGenerator(
        background=[
            "You are a Home Assistant agent.",
            "Your primary role is to choose the right intent name among those available based on the user query.",
        ],
        output_instructions=[
            "Select exactly one intent name from the available intents.",
            "Format output according to schema."
        ],
    )
)


#########################
# HOME ASSISTANT METHODS #
#########################
def invoke_intent(intent_name: str) -> Optional[str]:
    """
    Call Home Assistant's intent API with the given intent.
    """
    url = f"{Config.HOME_ASSISTANT_BASE_URL}/api/intent/handle"

    payload = {"name": intent_name}

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.HOME_ASSISTNAT_TOKEN}"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code in (200, 201):
        logger.info(f"Intent invoked successfully: {response.json()}")
        return f"Intent invoked successfully: {response.json()}"
    else:
        logger.error(f"Failed to invoke intent: {response.status_code} - {response.text}")
        return None



#####################
# DEMO EXECUTION #
#####################
if __name__ == "__main__":
    # Example 1: Turn on ceiling lights
    agent = AtomicAgent[HomeAssistantInputSchema, HomeAssistantOutputSchema](config=home_assistant_agent_config)
    agent.register_context_provider("available_intents", AvailableIntentsProvider("Available Intents"))
    output1 = agent.run(HomeAssistantInputSchema(user_query="Turn on the Keyboard Strip"))
    print(output1)

    # Example 2: Get temperature
    output2 = agent.run(HomeAssistantInputSchema(user_query="What is the temperature right now?"))
    print(output2)
