from datetime import time, timezone, timedelta
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, Defaults
from src.config import Config
from rich.console import Console
from src.logger import logger
from src.transcriber import OpenAITranscriber
from agents.orchestrator_agent import get_tool_name
from src.tools.searxng_search.tool.searxng_search import SearXNGSearchTool, SearXNGSearchToolConfig, SearXNGSearchToolInputSchema, SearXNGSearchToolOutputSchema
from src.agents.glados_responder_agent import get_final_glados_response
from src.agents.vikunja_agent import process_vikunja_query


console = Console()


class TelegramBot:
    def __init__(self, token):
        # Initialize the application with the provided token
        my_defaults = Defaults(tzinfo=timezone(timedelta(hours=2))) # Set tzinfo to UTC+1
        self.app = ApplicationBuilder().token(token).defaults(my_defaults).build()
        self.transcriber = OpenAITranscriber(Config.OPENAI_API_KEY)
        self.user_message_text: str = ""
        self.daily_job = None # To store the job object

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

    # New handler function for text messages
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
                    # Example: turn on lights, check temperature, etc.
                    await update.message.reply_text("Routing to Home Assistant Tool…")
                    # call_home_assistant_tool(self.user_message_text)

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

                    final_response = get_final_glados_response(self.user_message_text, formatted_results)
                    await update.message.reply_text(final_response)

                elif tool_name == "Vikunja Tool":
                    output = process_vikunja_query(self.user_message_text)
                    final_response = get_final_glados_response(self.user_message_text, output)
                    await update.message.reply_text(final_response)

                elif tool_name == "No Tool":
                    await update.message.reply_text("No tool required, handling as plain conversation.")
                    # Could just echo back or do nothing

                else:
                    await update.message.reply_text("Unknown tool detected.")



            else:
                # Reply to the user with a message indicating that the chat ID does not match
                console.print(f"[bold red]Chat ID {chat_id} does not match the configured chat ID[/bold red]")
                logger.warning(f"Chat ID {chat_id} does not match the configured chat ID")

    # New handler function for voice messages
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

    async def send_scheduled_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Send a scheduled message to the configured chat."""
        chat_id = Config.MY_CHAT_ID
        await context.bot.send_message(chat_id=chat_id, text="This is your scheduled message! ✅")

    async def check_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Command to check the next trigger time of the daily job."""
        if self.daily_job and self.daily_job.next_t:
            # next_t is a datetime.datetime object
            next_run_time = self.daily_job.next_t
            # Format the datetime object for display, including timezone info
            await update.message.reply_text(f"The daily message is scheduled to trigger next at: {next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        else:
            await update.message.reply_text("Daily job not found or not yet scheduled.")

    def setup_handlers(self):
        self.app.add_handler(CommandHandler("hello", self.hello))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.orchestrate_actions))
        self.app.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        self.app.add_handler(CommandHandler("check_schedule", self.check_schedule))
        
        self.daily_job = self.app.job_queue.run_daily( # Store the job object
            callback=self.send_scheduled_message,
            time=time(17, 11, 0),  # Set the time to 5:00 PM
            days=(0, 1, 2, 3, 4, 5, 6),  # Runs every day (Sunday=0, Saturday=6)
            chat_id=Config.MY_CHAT_ID,  # Associate the job with a specific chat ID
            name="daily_scheduled_message"  # Give your job a unique name
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