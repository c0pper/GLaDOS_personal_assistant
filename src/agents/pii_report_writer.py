import json
from typing import List, Optional, Dict, Any
from atomic_agents import AgentConfig, AtomicAgent, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, BaseDynamicContextProvider, ChatHistory
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI as OpenRouterClient
from datetime import datetime
from enum import Enum

from src.config import Config

########################
# INPUT/OUTPUT SCHEMAS #
########################
class UserProfileAnalyzerInputSchema(BaseIOSchema):
    """Input schema for the User Profile Analyzer Agent."""
    
    relevant_comments: List[str] = Field(
        ...,
        description="A list of relevant comments from the user to analyze for profiling"
    )

class PersonalityTrait(BaseModel):
    """Model for describing a personality trait."""
    trait: str = Field(..., description="The personality trait name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: List[str] = Field(..., description="Specific comments that demonstrate this trait")


class InterestCategory(Enum):
    """Categories of interests."""
    TECHNOLOGY = "technology"
    SCIENCE = "science"
    ARTS = "arts"
    SPORTS = "sports"
    GAMING = "gaming"
    POLITICS = "politics"
    FINANCE = "finance"
    HEALTH = "health"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    TRAVEL = "travel"
    FOOD = "food"
    OTHER = "other"


class UserInterest(BaseModel):
    """Model for describing a user's interest."""
    category: InterestCategory = Field(..., description="Category of interest")
    specific_topics: List[str] = Field(..., description="Specific topics within this category")
    frequency_score: float = Field(..., ge=0.0, le=1.0, description="How frequently this interest appears (0.0 to 1.0)")


class EmotionalPattern(BaseModel):
    """Model for describing emotional patterns."""
    dominant_emotion: str = Field(..., description="Most frequently observed emotion")
    emotional_range: List[str] = Field(..., description="Range of emotions expressed")
    emotional_stability_score: float = Field(..., ge=0.0, le=1.0, description="Consistency of emotional expression (0.0 to 1.0)")


class CommunicationStyle(BaseModel):
    """Model for describing communication style."""
    formality_level: str = Field(..., description="Formal, casual, or technical")
    vocabulary_complexity: str = Field(..., description="Simple, moderate, or advanced")
    tone_consistency: float = Field(..., ge=0.0, le=1.0, description="How consistent the tone is across comments")


class UserProfileReportOutputSchema(BaseIOSchema):
    """Output schema for the User Profile Analyzer Agent."""
    
    profile_summary: str = Field(
        ...,
        description="A concise summary of the user's overall profile"
    )
    
    personality_traits: List[PersonalityTrait] = Field(
        ...,
        description="List of identified personality traits with evidence"
    )
    
    key_interests: List[UserInterest] = Field(
        ...,
        description="List of user's primary interests and hobbies"
    )
    
    values_and_beliefs: List[str] = Field(
        ...,
        description="Core values, beliefs, or principles expressed"
    )
    
    emotional_patterns: EmotionalPattern = Field(
        ...,
        description="Analysis of emotional expression patterns"
    )
    
    communication_style: CommunicationStyle = Field(
        ...,
        description="Analysis of how the user communicates"
    )
    
    potential_demographics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inferred demographic information with confidence scores"
    )
    
    behavioral_patterns: List[str] = Field(
        ...,
        description="Notable behavioral patterns observed"
    )
    
    knowledge_domains: List[str] = Field(
        ...,
        description="Areas where user shows expertise or deep knowledge"
    )
    
    social_orientation: str = Field(
        ...,
        description="Social tendencies: introverted, extroverted, ambivert, etc."
    )
    
    profile_confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the profile accuracy based on available data"
    )
    
    limitations_and_caveats: List[str] = Field(
        ...,
        description="Limitations of the analysis and important caveats"
    )


########################
# USER PROFILE ANALYZER AGENT CONFIG #
########################
user_profile_analyzer_config = AgentConfig(
    client=instructor.from_openai(
        OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY
        ),
    ),
    model=Config.RESPONDER_AGENT_MODEL,
    history=ChatHistory(max_messages=10),
    system_prompt_generator=SystemPromptGenerator(
        background=[
            "You are a professional behavioral analyst and psychologist specializing in digital footprint analysis.",
            "Your expertise is in analyzing text communications to build comprehensive user profiles.",
            "You combine psychological principles, linguistic analysis, and behavioral science to create accurate profiles.",
            "You maintain scientific rigor while being practical and actionable in your analysis.",
            "You understand the limitations of text-based analysis and always include appropriate caveats.",
            "Your goal is to provide insightful, evidence-based profiles that respect privacy while offering valuable insights.",
            "Output must be in valid JSON format with the specified schema.",
        ],
        output_instructions=[
            "Analyze the provided user comments to build a comprehensive psychological and behavioral profile.",
            "Use evidence-based psychological frameworks and linguistic analysis techniques.",
            
            "ANALYSIS FRAMEWORK:",
            "1. PERSONALITY TRAITS:",
            "   - Analyze using Big Five (OCEAN) framework: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism",
            "   - Identify specific traits with direct evidence from comments",
            "   - Provide confidence scores based on evidence strength",
            
            "2. INTERESTS AND EXPERTISE:",
            "   - Identify recurring topics and subject matter",
            "   - Categorize interests using the provided categories",
            "   - Note areas of demonstrated expertise or deep knowledge",
            
            "3. VALUES AND BELIEFS:",
            "   - Extract expressed values, principles, and moral stances",
            "   - Identify political, philosophical, or religious leanings if evident",
            "   - Note consistency or contradictions in stated beliefs",
            
            "4. EMOTIONAL PATTERNS:",
            "   - Analyze emotional vocabulary and expression",
            "   - Identify dominant emotional states",
            "   - Assess emotional stability and range",
            
            "5. COMMUNICATION STYLE:",
            "   - Analyze language complexity and vocabulary",
            "   - Assess formality and tone",
            "   - Note persuasive techniques or argumentation style",
            
            "6. BEHAVIORAL PATTERNS:",
            "   - Identify patterns in how the user interacts with others",
            "   - Note tendencies in argumentation, agreement, or dissent",
            "   - Observe consistency in posting patterns if timestamps available",
            
            "7. SOCIAL ORIENTATION:",
            "   - Assess social tendencies based on interaction patterns",
            "   - Note leadership, collaborative, or confrontational tendencies",
            
            "EVIDENCE REQUIREMENTS:",
            "- Every claim must be supported by specific quotes or paraphrases",
            "- Use exact phrases from comments when possible",
            "- Note the context of each piece of evidence",
            
            "LIMITATIONS AND CAVEATS:",
            "- Acknowledge the limitations of text-only analysis",
            "- Note when sample size is small or unrepresentative",
            "- Distinguish between stated opinions and actual behavior",
            "- Avoid overgeneralization from limited data",
            
            "OUTPUT REQUIREMENTS:",
            "1. Return a complete JSON object matching the output schema exactly",
            "2. All fields must be populated with appropriate data types",
            "3. 'profile_confidence_score' must reflect the quality and quantity of available data",
            "4. 'limitations_and_caveats' must include at least 3 relevant limitations",
            "5. Provide specific evidence for personality traits and behavioral patterns",
            "6. Use proper enum values for interest categories",
            
            "EXAMPLE OUTPUT STRUCTURE:",
            "{",
            '  "profile_summary": "A concise summary...",',
            '  "personality_traits": [',
            '    {',
            '      "trait": "curious",',
            '      "confidence": 0.85,',
            '      "evidence": ["User asked detailed questions about...", "Expressed interest in learning..."]',
            "    }",
            "  ],",
            '  "key_interests": [',
            '    {',
            '      "category": "technology",',
            '      "specific_topics": ["machine learning", "python programming"],',
            '      "frequency_score": 0.9',
            "    }",
            "  ],",
            '  "values_and_beliefs": ["Value evidence-based reasoning", "Support for open source software"],',
            '  "emotional_patterns": {',
            '    "dominant_emotion": "analytical",',
            '    "emotional_range": ["curious", "frustrated", "satisfied"],',
            '    "emotional_stability_score": 0.8',
            "  },",
            '  "communication_style": {',
            '    "formality_level": "technical",',
            '    "vocabulary_complexity": "advanced",',
            '    "tone_consistency": 0.75',
            "  },",
            '  "potential_demographics": {"estimated_age_range": "25-35", "confidence": 0.6},',
            '  "behavioral_patterns": ["Prefers detailed explanations", "Frequently asks clarifying questions"],',
            '  "knowledge_domains": ["computer science", "data analysis"],',
            '  "social_orientation": "introverted",',
            '  "profile_confidence_score": 0.7,',
            '  "limitations_and_caveats": ["Limited sample size", "No demographic information provided", "Analysis based only on Reddit comments"]',
            "}"
        ],
    ),
)

user_profile_analyzer_agent = AtomicAgent[UserProfileAnalyzerInputSchema, UserProfileReportOutputSchema](config=user_profile_analyzer_config)

class UserProfileAnalyzer():
    def __init__(self, config: AgentConfig):
        self.agent = AtomicAgent[UserProfileAnalyzerInputSchema, UserProfileReportOutputSchema](config=config)

    def run_and_generate_markdown_report(self, user_messages: UserProfileAnalyzerInputSchema) -> str:
        analysis = self.agent.run(user_messages)
        return self.generate_markdown_report(analysis)

    @staticmethod
    def generate_markdown_report(analysis: UserProfileReportOutputSchema) -> str:
        """
        Generates a comprehensive Markdown report from the analysis.
        
        Args:
            analysis: UserProfileReportOutputSchema object
            
        Returns:
            Formatted Markdown string
        """
        markdown_parts = []
        
        # Header
        markdown_parts.append("# 📊 User Profile Analysis Report\n")
        markdown_parts.append(f"*Analysis Confidence: {analysis.profile_confidence_score:.0%}*\n")
        
        # 1. Executive Summary
        markdown_parts.append("## 📋 Executive Summary")
        markdown_parts.append(f"{analysis.profile_summary}\n")
        
        # 2. Personality Profile
        markdown_parts.append("## 🧠 Personality Profile")
        if analysis.personality_traits:
            markdown_parts.append("### Dominant Personality Traits")
            for trait in analysis.personality_traits:
                stars = "⭐" * int(trait.confidence * 5)
                markdown_parts.append(f"- **{trait.trait.title()}** ({trait.confidence:.0%} confidence) {stars}")
                if trait.evidence:
                    markdown_parts.append("  *Evidence:*")
                    for evidence in trait.evidence[:3]:  # Show top 3 pieces of evidence
                        markdown_parts.append(f"    - {evidence}")
        markdown_parts.append("")
        
        # 3. Interests & Expertise
        markdown_parts.append("## 🎯 Interests & Expertise")
        if analysis.key_interests:
            markdown_parts.append("### Primary Interest Areas")
            for interest in analysis.key_interests:
                frequency_bar = "▓" * int(interest.frequency_score * 10) + "░" * (10 - int(interest.frequency_score * 10))
                markdown_parts.append(f"- **{interest.category.value.title()}** (Frequency: {interest.frequency_score:.0%})")
                markdown_parts.append(f"  `{frequency_bar}`")
                if interest.specific_topics:
                    topics = ", ".join(interest.specific_topics[:5])  # Limit to 5 topics
                    markdown_parts.append(f"  *Topics:* {topics}")
        markdown_parts.append("")
        
        if analysis.knowledge_domains:
            markdown_parts.append("### Knowledge Domains")
            for domain in analysis.knowledge_domains:
                markdown_parts.append(f"- {domain}")
        markdown_parts.append("")
        
        # 4. Values & Beliefs
        markdown_parts.append("## 💭 Values & Beliefs")
        if analysis.values_and_beliefs:
            for value in analysis.values_and_beliefs:
                markdown_parts.append(f"- {value}")
        markdown_parts.append("")
        
        # 5. Communication Style
        markdown_parts.append("## 💬 Communication Style")
        if analysis.communication_style:
            comm = analysis.communication_style
            consistency_bar = "█" * int(comm.tone_consistency * 10) + "░" * (10 - int(comm.tone_consistency * 10))
            
            markdown_parts.append(f"- **Formality Level:** {comm.formality_level.title()}")
            markdown_parts.append(f"- **Vocabulary Complexity:** {comm.vocabulary_complexity.title()}")
            markdown_parts.append(f"- **Tone Consistency:** {comm.tone_consistency:.0%}")
            markdown_parts.append(f"  `{consistency_bar}`")
        markdown_parts.append("")
        
        # 6. Emotional Patterns
        markdown_parts.append("## 😊 Emotional Patterns")
        if analysis.emotional_patterns:
            emotions = analysis.emotional_patterns
            stability_bar = "█" * int(emotions.emotional_stability_score * 10) + "░" * (10 - int(emotions.emotional_stability_score * 10))
            
            markdown_parts.append(f"- **Dominant Emotion:** {emotions.dominant_emotion.title()}")
            markdown_parts.append(f"- **Emotional Range:** {', '.join(emotions.emotional_range)}")
            markdown_parts.append(f"- **Emotional Stability:** {emotions.emotional_stability_score:.0%}")
            markdown_parts.append(f"  `{stability_bar}`")
        markdown_parts.append("")
        
        # 7. Behavioral Patterns
        markdown_parts.append("## 🔄 Behavioral Patterns")
        if analysis.behavioral_patterns:
            for pattern in analysis.behavioral_patterns:
                markdown_parts.append(f"- {pattern}")
        markdown_parts.append("")
        
        # 8. Social Orientation
        markdown_parts.append("## 👥 Social Orientation")
        markdown_parts.append(f"- **Social Tendency:** {analysis.social_orientation.title()}")
        markdown_parts.append("")
        
        # 9. Demographic Insights
        markdown_parts.append("## 👤 Demographic Insights")
        if analysis.potential_demographics:
            for key, value in analysis.potential_demographics.items():
                if isinstance(value, dict) and 'confidence' in value:
                    confidence = value['confidence']
                    del value['confidence']
                    markdown_parts.append(f"- **{key.replace('_', ' ').title()}:** {json.dumps(value)} (Confidence: {confidence:.0%})")
                else:
                    markdown_parts.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        else:
            markdown_parts.append("*Limited demographic information could be inferred from the data.*")
        markdown_parts.append("")
        
        # 10. Limitations & Caveats
        markdown_parts.append("## ⚠️ Limitations & Caveats")
        markdown_parts.append("*Important considerations for interpreting this analysis:*")
        for limitation in analysis.limitations_and_caveats:
            markdown_parts.append(f"- {limitation}")
        markdown_parts.append("")
        
        # 11. Technical Details
        markdown_parts.append("## 🔧 Technical Details")
        markdown_parts.append(f"- **Analysis Confidence:** {analysis.profile_confidence_score:.0%}")
        markdown_parts.append("")
        
        return "\n".join(markdown_parts)


if __name__ == "__main__":
    relevant_comments = [
        "I am a software engineer with a passion for data analysis and machine learning.",
        "I enjoy working on projects that involve complex algorithms and large datasets.",
        "I am always looking for opportunities to improve my skills and knowledge.",
        "I believe in the power of open-source software and contributing to the community.",
        "I am excited to learn more about the latest trends in data science and AI.",
        "I value collaboration and teamwork, and I am always open to working with others.",
        "I believe in the importance of continuous learning and improvement.",
        "I am committed to staying up-to-date with the latest technologies and trends.",
        "I enjoy exploring new technologies and tools, and I am always looking for ways to enhance my skills.",
        "I believe in the power of data to drive innovation and make a positive impact on society.",
        "I am always looking for ways to solve complex problems and make a difference.",
        "I value creativity and imagination, and I am always open to new ideas and perspectives.",
        "I believe in the importance of ethical and responsible use of technology.",
    ]
    analyzer = UserProfileAnalyzer(config=user_profile_analyzer_config)
    markdown = analyzer.run_and_generate_markdown_report(UserProfileAnalyzerInputSchema(relevant_comments=relevant_comments))
    print(markdown)
