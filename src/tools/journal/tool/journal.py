
from datetime import datetime
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, Defaults
from src.config import Config
from src.logger import logger
from src.tools.journal.tool.postgres_db import PostgresDB

class JournalEntry(BaseModel):
    id: str
    date: str
    mood: int = 0
    people: List[str] = []
    notes: str = ""

    def __str__(self):
        return f"Journal Entry: {self.id} - Mood: {self.mood} - People: {self.people} - Notes: {self.notes}"

class Journal:
    """
    Manages the bot's journal functionality, including handling user input,
    interacting with the database, and building responses.
    """
    def __init__(self, db: PostgresDB):
        self.db = db
        self.journal_table = "journal"
        self.people = self.db.get_all_people()
        self.current_journal_entry: Optional[JournalEntry] = None

    def get_people_keyboard_with_id(self, journal_id: str) -> InlineKeyboardMarkup:
        """Generates an inline keyboard for selecting people, including the journal ID."""
        people_rows = []
        max_buttons_per_row = 4
        for i in range(0, len(self.people), max_buttons_per_row):
            row_slice = self.people[i:i + max_buttons_per_row]
            # Include the journal ID in the callback data
            buttons = [InlineKeyboardButton(person.title(), callback_data=f"person;{person};{journal_id}") for person in row_slice]
            people_rows.append(buttons)
        
        # Add the 'Done' button with the journal ID
        people_rows.append([InlineKeyboardButton("Done", callback_data=f"done_people;done_people;{journal_id}")])
        
        return InlineKeyboardMarkup(people_rows)

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the initial /journal command."""
        chat_id = Config.MY_CHAT_ID
        new_journal_entry_id = datetime.now().strftime('%d%m%Y')

        # Initialize Pydantic model
        self.current_journal_entry = JournalEntry(
            id=new_journal_entry_id,
            date=datetime.now().isoformat(),
            mood=0,
            people=[],
            notes=""
        )
        
        # self.pending_entries[new_journal_entry_id] = journal_entry

        # Check if today's entry already exists
        today_entry = self.db.select_row_by_id(self.journal_table, new_journal_entry_id)
        if not today_entry:
            # Initialize a new journal entry for the day
            self.db.insert_row(self.journal_table, {
                'id': new_journal_entry_id,
                'date': datetime.now().isoformat(),
                'mood': 0,
                'people': '',
                'notes': ''
            })

        # Ask the user for their mood with inline buttons
        inline_keyboard = [
            [
                {"text": "😭", "callback_data": f"mood;1;{new_journal_entry_id}"},
                {"text": "😢", "callback_data": f"mood;2;{new_journal_entry_id}"},
                {"text": "😐", "callback_data": f"mood;3;{new_journal_entry_id}"},
                {"text": "🙂", "callback_data": f"mood;4;{new_journal_entry_id}"},
                {"text": "🤩", "callback_data": f"mood;5;{new_journal_entry_id}"}
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
        # Split the callback data to get the type and the journal ID
        callback_parts = query.data.split(';')
        data_type = callback_parts[0]
        callback_value = callback_parts[1]
        journal_id = callback_parts[2]

        # journal_entry = self.pending_entries.get(journal_id)

        # Initialize variables for the updated journal entry
        mood_value = 0
        current_people_str = ''
        notes_value = 'No notes'

        # Answer the callback query to remove the loading state on the button
        await query.answer()

        # Logic based on the n8n flow's "Switch1" node
        if data_type == 'mood':
            # Mood selection: update mood column and proceed to ask about people
            mood_value = int(callback_value)
            self.current_journal_entry.mood = mood_value
            self.db.update_row(self.journal_table, journal_id, {'mood': mood_value})
            
            # The people keyboard also needs to send the journal_id
            updated_people_keyboard = self.get_people_keyboard_with_id(journal_id)

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Who were you with?",
                reply_markup=updated_people_keyboard  # Get the people selection keyboard
            )

        elif data_type == 'done_people':
            # People selection is complete, ask for notes
            notes_keyboard = [
                [InlineKeyboardButton("No notes", callback_data=f"no_notes;none;{journal_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(notes_keyboard)
            
            self.current_journal_entry.notes = notes_value

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Add a note by replying to this message or click No notes",
                reply_markup=reply_markup
            )

        elif data_type == 'no_notes':
            # Final flow: end the conversation
            print(self.current_journal_entry)
            self.post_journal_entry()
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Journal entry saved.\n{str(self.current_journal_entry)}"
            )

        elif data_type == 'person':
            # Check if the person is already in the list.
            if callback_value in self.current_journal_entry.people:
                # If the person is found, remove them.
                self.current_journal_entry.people.remove(callback_value)
                logger.info(f"Removed {callback_value} from the list.")
            else:
                # If the person is not found, add them to the list.
                self.current_journal_entry.people.append(callback_value)
                logger.info(f"Added {callback_value} to the list.")

            # Join the updated list back into a semicolon-separated string.
            new_people_str = '; '.join(self.current_journal_entry.people)
            
            # Update the 'people' column in the database with the new string.
            self.db.update_row(self.journal_table, journal_id, {'people': new_people_str})

            # Prepare the text for the updated message.
            # Check if there are any people currently selected.
            if self.current_journal_entry.people:
                selected_people_text = ", ".join(self.current_journal_entry.people)
                new_message_text = f"Who were you with? (Currently selected: {selected_people_text})"
            else:
                new_message_text = "Who were you with?"
            
            # The people keyboard also needs to send the journal_id
            updated_people_keyboard = self.get_people_keyboard_with_id(journal_id)

            # Edit the message to show the updated selection and the keyboard.
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_message_text,
                reply_markup=updated_people_keyboard
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles a regular text message from the user."""
        message = update.message
        text = message.text
        # Check if the message is a reply to the 'notes' message
        if message.reply_to_message and "Add a note by replying" in message.reply_to_message.text:
            journal_id = datetime.now().strftime('%d%m%Y')
            self.current_journal_entry.notes = text

            self.db.update_row(self.journal_table, journal_id, {'notes': text})
            await self.post_journal_entry()

            # Final flow
            await context.bot.send_message(chat_id=message.chat_id, text="Note added. Journal entry complete.\n\n" + str(self.current_journal_entry))
            # Delete the original "Add a note" message
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.reply_to_message.message_id)
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)

    async def post_journal_entry(self):
        """Posts the current journal entry to the Journiv."""
        print(f"Posting journal entry: {self.current_journal_entry}")