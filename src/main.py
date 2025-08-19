from datetime import time, timezone, timedelta
import json
from atomic_agents import AtomicAgent
import requests
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, Defaults, CallbackQueryHandler
from src.config import Config
from rich.console import Console
from src.logger import logger
from src.transcriber import OpenAITranscriber
from agents.orchestrator_agent import get_tool_name
from src.tools.searxng_search.tool.searxng_search import SearXNGSearchTool, SearXNGSearchToolConfig, SearXNGSearchToolInputSchema, SearXNGSearchToolOutputSchema
from src.agents.glados_responder_agent import GladosResponderInputSchema, GladosResponderOutputSchema, glados_responder_config
from src.agents.vikunja_agent import process_vikunja_query
from src.agents.home_assistant_agent import HomeAssistantInputSchema, HomeAssistantOutputSchema, invoke_intent, home_assistant_agent_config, AvailableIntentsProvider
from src.tools.journal.tool.journal import Journal
from src.tools.journal.tool.postgres_db import PostgresDB


console = Console()


class TelegramBot:
    def __init__(self, token):
        # Initialize the application with the provided token
        my_defaults = Defaults(tzinfo=timezone(timedelta(hours=2))) # Set tzinfo to UTC+1
        self.app = ApplicationBuilder().token(token).defaults(my_defaults).build()
        self.transcriber = OpenAITranscriber(Config.OPENAI_API_KEY)
        self.user_message_text: str = ""
        self.daily_job = None # To store the job object
        self.respoder_agent = AtomicAgent[GladosResponderInputSchema, GladosResponderOutputSchema](config=glados_responder_config)
        self.home_assistant_agent = AtomicAgent[HomeAssistantInputSchema, HomeAssistantOutputSchema](config=home_assistant_agent_config)
        self.home_assistant_agent.register_context_provider("available_intents", AvailableIntentsProvider("Available Intents"))
        self.journal_db = PostgresDB(
            db_name=Config.POSTGRES_DB_NAME,
            user=Config.POSTGRES_DB_USER,
            password=Config.POSTGRES_DB_PASSWORD,
            host=Config.POSTGRES_DB_HOST,
            port=Config.POSTGRES_DB_PORT
        )
        self.journal_app = Journal(db=self.journal_db)

    def check_chat_id(self, chat_id):
        """
        Checks if the provided chat_id matches the hardcoded chat ID.
        This conceptually represents a filter node in the n8n flow.
        
        Args:
            chat_id (str or int): The chat ID from the incoming message.
        
        Returns:
            bool: True if the chat ID matches, False otherwise.
        """
        target_chat_id = Config.MY_CHAT_ID
        return chat_id == target_chat_id

    async def hello(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Respond with a greeting message including the user's first name
        await update.message.reply_text(f'Hello {update.effective_user.first_name}')

    async def orchestrate_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Echoes the user's text message."""
        if update.message and update.message.text:
            # Check if the chat ID matches the configured one
            chat_id = update._effective_message.chat_id
            if self.check_chat_id(chat_id):
                text = update.message.text
                self.user_message_text = text

                # Process the user message and get the tool name
                tool_name = get_tool_name(self.user_message_text)
                logger.info(f"Detected tool: {tool_name} for message: {self.user_message_text}")


                # Handle each case
                if tool_name == "Home Assistant Tool":
                    output = self.home_assistant_agent.run(
                        HomeAssistantInputSchema(user_query=self.user_message_text)
                    ).intent_name.name

                    tool_output = invoke_intent(output)

                    final_response = self.respoder_agent.run(
                        GladosResponderInputSchema(chat_message=self.user_message_text, tool_result=tool_output)
                    ).final_response

                elif tool_name == "SearXNG Tool":
                    search_tool_instance = SearXNGSearchTool(
                        config=SearXNGSearchToolConfig()
                    )
                    search_input = SearXNGSearchToolInputSchema(
                        queries=[self.user_message_text],
                        # category="news",
                    )
                    output: SearXNGSearchToolOutputSchema = search_tool_instance.run(search_input)
                    formatted_results = await search_tool_instance.format_results(output.results)

                    final_response = self.respoder_agent.run(
                        GladosResponderInputSchema(chat_message=self.user_message_text, tool_result=formatted_results)
                    ).final_response

                elif tool_name == "Vikunja Tool":
                    output = process_vikunja_query(self.user_message_text)
                    final_response = self.respoder_agent.run(
                        GladosResponderInputSchema(chat_message=self.user_message_text, tool_result=output)
                    ).final_response

                elif tool_name == "No Tool":
                    final_response = self.respoder_agent.run(
                        GladosResponderInputSchema(chat_message=self.user_message_text, tool_result=None)
                    ).final_response

                else:
                    logger.warning(f"Unknown tool detected: {tool_name}")
                    final_response = self.respoder_agent.run(
                        GladosResponderInputSchema(chat_message=self.user_message_text, tool_result=f"Unknown tool detected: {tool_name}")
                    ).final_response

                await update.message.reply_text(final_response)
                await self.send_voice_response(update, context, final_response)


            else:
                # Reply to the user with a message indicating that the chat ID does not match
                console.print(f"[bold red]Chat ID {chat_id} does not match the configured chat ID[/bold red]")
                logger.warning(f"Chat ID {chat_id} does not match the configured chat ID")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Responds to a voice message by echoing it back."""
        voice_file = update.message.voice
        if voice_file:
            file_obj = await voice_file.get_file() # [3, 4]
            voice_data_bytes = await file_obj.download_as_bytearray()

            # Transcribe the voice message using OpenAI Whisper
            transcribed_text = self.transcriber.transcribe(voice_data_bytes)
            self.user_message_text = transcribed_text

        else:
            await update.message.reply_text("I received a message, but it wasn't a voice message")

    async def send_voice_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Sends a voice response to the user."""
        url = f"{Config.HOME_ASSISTANT_BASE_URL}/api/tts_get_url"

        payload = {
            "engine_id": "tts.piper",
            "message": text,
            "options": {
                "voice": "glados"
            }
        }

        headers = {
            "Authorization": f"Bearer {Config.HOME_ASSISTNAT_TOKEN}"
        }

        response_from_tts_service = requests.post(url, json=payload, headers=headers)

        if response_from_tts_service.status_code in (200, 201):
            tts_mp3_url = response_from_tts_service.json().get("url")
            logger.info(f"Successfully invoked TTS service. MP3 URL obtained: {tts_mp3_url}")

            if tts_mp3_url:
                try:
                    response_mp3_content = requests.get(tts_mp3_url, stream=True)
                    response_mp3_content.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

                    # 'delete=True' (default) ensures the file is automatically removed when closed
                    # 'suffix=".mp3"' helps in identifying the file type
                    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as temp_file:
                        # Write the downloaded content in chunks to the temporary file
                        for chunk in response_mp3_content.iter_content(chunk_size=8192):
                            temp_file.write(chunk)
                        temp_file.flush() # Ensure all data is written to the underlying file system
                        temp_file.seek(0) # Rewind the file pointer to the beginning for reading by telegram-bot

                        logger.info(f"Downloaded MP3 content to temporary file: {temp_file.name}")

                        # Step 4: Pass the temporary file object to reply_voice
                        await update.message.reply_voice(voice=temp_file)
                        logger.info("Voice message successfully sent from temporary file.")

                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to download MP3 from {tts_mp3_url}: {e}")
                    await update.message.reply_text("Sorry, I encountered an error while retrieving the voice message.")
                    return None
                except Exception as e:
                    logger.error(f"An unexpected error occurred during voice file processing: {e}")
                    await update.message.reply_text("An unexpected error occurred while sending the voice message.")
                    return None
            else:
                logger.error("No valid MP3 URL was returned by the TTS service.")
                await update.message.reply_text("Sorry, I couldn't get a valid voice message URL.")
                return None
        else:
            logger.error(f"Failed to invoke TTS service: {response_from_tts_service.status_code} - {response_from_tts_service.text}")
            await update.message.reply_text("Sorry, the voice generation service is currently unavailable.")
            return None

    async def send_journal_reminder(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a scheduled message to the configured chat."""
        await context.bot.send_message(chat_id=Config.MY_CHAT_ID, text="This is your scheduled message! ✅")

    def setup_handlers(self):
        """Sets up and registers all the bot's handlers."""
        # Journal-related handlers should be registered first because they are more specific.
        self.app.add_handler(CommandHandler("journal", self.journal_app.handle_command))
        self.app.add_handler(CallbackQueryHandler(self.journal_app.handle_callback_query))
        
        # This handler is now much more specific and won't conflict.
        # It will only trigger for text messages that are also replies.
        self.app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, self.journal_app.handle_message))

        # Add your more general handlers after the specific ones
        self.app.add_handler(CommandHandler("hello", self.hello))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.orchestrate_actions))
        self.app.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        
        # Set up daily journal reminder
        self.daily_job = self.app.job_queue.run_daily(
            callback=self.send_journal_reminder,
            time=time(17, 11, 0),
            days=(0, 1, 2, 3, 4, 5, 6),
            chat_id=Config.MY_CHAT_ID,
            name="daily_journal_reminder"
        )

        console.print("[bold green]Handlers have been set up successfully![/bold green]")
        
    def run(self):
        # Run the bot using polling
        console.print("[bold green]Starting Telegram Bot...[/bold green]")
        self.setup_handlers()
        # It's recommended to pass allowed_updates=Update.ALL_TYPES for comprehensive update handling [5-12].
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)




# Example usage to demonstrate integration
if __name__ == "__main__":
    
    # Initialize the Telegram bot with the token from the config
    telegram_bot = TelegramBot(Config.TELEGRAM_TOKEN)
    telegram_bot.run()