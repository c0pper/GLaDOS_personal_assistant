from typing import List, Optional
from atomic_agents import AgentConfig, AtomicAgent, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, BaseDynamicContextProvider, ChatHistory
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI as OpenRouterClient

from src.config import Config

########################
# INPUT/OUTPUT SCHEMAS #
########################
class PersonalInfoIdentifierInputSchema(BaseIOSchema):
    """Input schema for the Personal Information Identifier Agent."""

    user_messages: str = Field(..., description="The user messages numbered from 0 to n.")

  
class PersonalInfoIdentifierOutputSchema(BaseIOSchema):
    """Output schema for the Personal Information Identifier Agent."""
    
    items_found_indexes: List[int] = Field(
        ..., 
        description="List of indexes of user messages that contain personal information"
    )

########################
# PERSONAL INFO IDENTIFIER AGENT CONFIG #
########################
personal_info_identifier_config = AgentConfig(
    client=instructor.from_openai(
        OpenRouterClient(base_url="https://openrouter.ai/api/v1", api_key=Config.OPENROUTER_API_KEY),
    ),
    model=Config.RESPONDER_AGENT_MODEL,  # Or use a specific model for this task
    history=ChatHistory(max_messages=10),
    system_prompt_generator=SystemPromptGenerator(
        background=[
            "You are a privacy and security expert specializing in personal information identification.",
            "Your task is to scan text content for any personal information that could compromise someone's privacy or security.",
            "Be thorough and meticulous - even seemingly harmless details can be identifying when combined.",
            "Your analysis will help users identify and delete sensitive information to protect themselves.",
            "Output must be in valid JSON format with the specified schema.",
        ],
        output_instructions=[
            "Carefully analyze the provided user messages for personal information across all categories.",
            "For each identified item, extract the corresponding index.",
            "Types of PII to consider:",
            "1. TOP PRIORITY: Biographical & Demographic Data: Age, gender, race, religion, politics, education",
            "2. Personally Identifiable Information (PII): Full name, address, phone, email, DOB, government IDs",
            "3. Geographical & Locational Data: Cities, regions, landmarks, frequent locations, travel plans",
            "4. Professional & Occupational Information: Employer, job title, specific projects, work schedule",
            "5. Financial & Economic Data: Income, debt, banks, investments, financial struggles",
            "6. Relationship & Social Graph Data: Family, friends, colleagues, their details",
            "7. Medical & Health Information: Conditions, medications, treatments, mental health, substance use",
            "8. Psychological & Behavioral Profile: Beliefs, fears, hobbies, personality traits, emotional states",
            "9. Routine & Habitual Data: Daily schedules, routines, habits, media consumption",
            
            "CRITERIA:",
            "- Include items that directly reveal personal information",
            "- Include only items that could directly be used for profiling or tracking",
            
            "OUTPUT REQUIREMENTS:",
            "1. Return a JSON object matching the output schema exactly",
            "2. 'items_found_indexes' should be an array of integers representing the indexes of messages containing personal information",
            "3. If no personal information is found, return empty array for 'items_found_indexes'",
            
            "EXAMPLE OUTPUT STRUCTURE:",
            '{',
            '  "items_found_indexes": [1, 3],',
            '}'
        ],
    ),
)

class PersonalInfoIdentifierAgent():
    def __init__(self, config: AgentConfig):
        self.agent = AtomicAgent[PersonalInfoIdentifierInputSchema, PersonalInfoIdentifierOutputSchema](config=config)


if __name__ == "__main__":
    def filter_messages(user_messages: str, items_found_indexes: List[int]) -> str:
        """
        Filter the user messages to only include the ones that do not contain personal information.
        """
        filtered_user_messages = []
        for i, msg in enumerate(user_messages.split("\n")):
            if i in items_found_indexes:
                filtered_user_messages.append(msg)
        return "\n".join(filtered_user_messages)
    
    personal_info_identifier = PersonalInfoIdentifierAgent(config=personal_info_identifier_config)

    user_messages=[
        "My email is john.doe@example.com",
        "I usually go to the gym on Main Street every morning",
        "Reveals daily routine and specific location pattern",
        "I am provided the user's query and the tool result, present the result as a single final reply.",
        "Your response will be spoken aloud, so avoid markdown or formatting.",
        "Always reply in English.",
        "You address the user as 'test subject', but do it only when necessary.",
    ]

    numbered_user_messages = "\n".join([f"{i}: {msg}" for i, msg in enumerate(user_messages)])
    
    analysis_result = personal_info_identifier.agent.run(
        PersonalInfoIdentifierInputSchema(
            user_messages=numbered_user_messages
        )
    )
    
    filtered_user_messages = filter_messages(
        user_messages=numbered_user_messages,
        items_found_indexes=analysis_result.items_found_indexes
    )
    print(filtered_user_messages)