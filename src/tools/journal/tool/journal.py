
from datetime import datetime
import os
from typing import Any, Dict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, Defaults
from src.logger import logger
from src.tools.journal.tool.postgres_db import PostgresDB


class Journal:
    """
    Manages the bot's journal functionality, including handling user input,
    interacting with the database, and building responses.
    """
    def __init__(self, db: PostgresDB):
        self.db = db
        self.journal_table = "journal"
        self.people = self.db.get_all_people()
        self.people_keyboard = self.get_people_keyboard()

    def get_people_keyboard(self) -> InlineKeyboardMarkup:
        """Generates an inline keyboard for selecting people."""
        people_rows = []
        max_buttons_per_row = 4
        for i in range(0, len(self.people), max_buttons_per_row):
            row_slice = self.people[i:i + max_buttons_per_row]
            buttons = [InlineKeyboardButton(person.title(), callback_data=person) for person in row_slice]
            people_rows.append(buttons)
        
        # Add the 'Done' button as a separate row at the end
        people_rows.append([InlineKeyboardButton("Done", callback_data="done_people")])
        
        return InlineKeyboardMarkup(people_rows)

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the initial /journal command."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        journal_id = datetime.now().strftime('%d%m%Y')

        # Check if today's entry already exists
        # today_entry = self.db.select_row_by_id(self.journal_table, journal_id)
        # if not today_entry:
        # Initialize a new journal entry for the day
        self.db.insert_row(self.journal_table, {
            'id': journal_id,
            'date': datetime.now().isoformat(),
            'mood': 0,
            'people': '',
            'notes': ''
        })

        # Ask the user for their mood with inline buttons
        inline_keyboard = [
            [
                {"text": "😭", "callback_data": "1"},
                {"text": "😢", "callback_data": "2"},
                {"text": "😐", "callback_data": "3"},
                {"text": "🙂", "callback_data": "4"},
                {"text": "🤩", "callback_data": "5"}
            ]
        ]
        # Using reply_markup with a list of lists of InlineKeyboardButton objects
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn['text'], callback_data=btn['callback_data']) for btn in row] for row in inline_keyboard])
        
        await context.bot.send_message(chat_id=chat_id, text="How are you feeling today?", reply_markup=reply_markup)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles callback queries from inline buttons."""
        query = update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        callback_data = query.data
        journal_id = datetime.now().strftime('%d%m%Y')

        # Answer the callback query to remove the loading state on the button
        await query.answer()

        # Logic based on the n8n flow's "Switch1" node
        if callback_data.isdigit():
            # Mood selection: update mood column and proceed to ask about people
            mood_value = int(callback_data)
            self.db.update_row(self.journal_table, journal_id, {'mood': mood_value})
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Who were you with?",
                reply_markup=self.people_keyboard  # Get the people selection keyboard
            )

        elif callback_data == 'done_people':
            # People selection is complete, ask for notes
            notes_keyboard = [
                [InlineKeyboardButton("No notes", callback_data="no_notes")]
            ]
            reply_markup = InlineKeyboardMarkup(notes_keyboard)
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Add a note by replying to this message or click No notes",
                reply_markup=reply_markup
            )

        elif callback_data == 'no_notes':
            # Final flow: end the conversation
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Journal entry saved. Have a great day!"
            )

        elif callback_data.lower() in self.people:
            # Add person to the people column
            current_entry = self.db.select_row_by_id(self.journal_table, journal_id)
            current_people_str = current_entry.get('people', '')
            # Split the string into a list of people.
            current_people_list = [p.strip() for p in current_people_str.split('; ') if p.strip()]
    
            # Check if the person is already in the list.
            if callback_data in current_people_list:
                # If the person is found, remove them.
                current_people_list.remove(callback_data)
                logger.info(f"Removed {callback_data} from the list.")
            else:
                # If the person is not found, add them to the list.
                current_people_list.append(callback_data)
                logger.info(f"Added {callback_data} to the list.")

            # Join the updated list back into a semicolon-separated string.
            new_people_str = '; '.join(current_people_list)
            
            # Update the 'people' column in the database with the new string.
            self.db.update_row(self.journal_table, journal_id, {'people': new_people_str})

            # Prepare the text for the updated message.
            # Check if there are any people currently selected.
            if current_people_list:
                selected_people_text = ", ".join(current_people_list)
                new_message_text = f"Who were you with? (Currently selected: {selected_people_text})"
            else:
                new_message_text = "Who were you with?"
            
            # Edit the message to show the updated selection and the keyboard.
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_message_text,
                reply_markup=self.people_keyboard
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles a regular text message from the user."""
        message = update.message
        text = message.text
        # Check if the message is a reply to the 'notes' message
        if message.reply_to_message and "Add a note by replying" in message.reply_to_message.text:
            journal_id = datetime.now().strftime('%d%m%Y')
            self.db.update_row(self.journal_table, journal_id, {'notes': text})
            # Final flow
            await context.bot.send_message(chat_id=message.chat_id, text="Note added. Journal entry complete.")
            # Delete the original "Add a note" message
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.reply_to_message.message_id)
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
