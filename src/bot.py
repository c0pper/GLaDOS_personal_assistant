import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from src.config import Config
from rich.console import Console
from src.logger import logger
from src.transcriber import OpenAITranscriber


console = Console()


class TelegramBot:
    def __init__(self, token):
        # Initialize the application with the provided token
        self.app = ApplicationBuilder().token(token).build()
        self.transcriber = OpenAITranscriber(Config.OPENAI_API_KEY)
        self.user_message_text: str = ""

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
    async def echo_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Echoes the user's text message."""
        if update.message and update.message.text:
            # Check if the chat ID matches the configured one
            chat_id = update._effective_message.chat_id
            if self.check_chat_id(chat_id):
                text = update.message.text
                self.user_message_text = text


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

    def setup_handlers(self):
        # Add the /hello command handler to the application
        self.app.add_handler(CommandHandler("hello", self.hello))
        
        # Add a handler for normal text messages (excluding commands)
        # filters.TEXT allows messages that contain text [1, 2].
        # ~filters.COMMAND excludes messages that are commands [3, 4].
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo_text))

        # Add a handler for voice messages
        # filters.VOICE allows messages that contain telegram.Message.voice.
        self.app.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))


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