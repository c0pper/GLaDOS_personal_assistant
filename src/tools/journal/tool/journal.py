
from datetime import datetime, date, timedelta
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, Defaults
from src.config import Config
from src.logger import logger
from src.tools.journal.tool.postgres_db import PostgresDB
from src.tools.journal.tool.journiv import JournivClient
from src.tools.journal.tool.shared_schemas import EntryCreate, MoodLogCreate

class JournalEntry(BaseModel):
    id: str
    date: datetime
    mood: int = 0
    mood_id: str = ""
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
        # self.people = self.db.get_all_people()
        self.current_journal_entry: Optional[JournalEntry] = None
        self.journiv_client = JournivClient()
        self.journiv_client.login()
        self.people = [t.name for t in self.journiv_client.get_all_tags()]
        self.people.sort()

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
            date=datetime.now(),
            mood=0,
            people=[],
            notes=""
        )

        # Get all moods from Journiv
        all_moods = self.journiv_client.get_moods()
    
        # Group moods by category
        mood_categories = {}
        for mood in all_moods:
            if mood.category not in mood_categories:
                mood_categories[mood.category] = []
            mood_categories[mood.category].append(mood)
        
        # Create keyboard organized by category
        inline_keyboard = []
        
        max_buttons_per_row = 4
        
        # Define category order: negative, neutral, positive
        category_order = ['negative', 'neutral', 'positive']
        
        for category in category_order:
            if category in mood_categories:
                moods = mood_categories[category]
                # Split moods into rows of max 4 buttons
                for i in range(0, len(moods), max_buttons_per_row):
                    row = []
                    for mood in moods[i:i + max_buttons_per_row]:
                        numeric_value = self.journiv_client.convert_mood_to_numeric(mood.name)
                        callback_data = f"mood;{numeric_value}+{mood.id};{new_journal_entry_id}"
                        button = InlineKeyboardButton(f"{mood.icon} {mood.name}", callback_data=callback_data)
                        row.append(button)
                    inline_keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        
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

        # Initialize variables for the updated journal entry
        mood_value = 0
        # notes_value = 'No notes'

        # Answer the callback query to remove the loading state on the button
        await query.answer()

        # Logic based on the n8n flow's "Switch1" node
        if data_type == 'mood':
            # Mood selection: update mood column and proceed to ask about people
            mood_value, mood_id = callback_value.split('+')
            mood_value = int(mood_value)
            self.current_journal_entry.mood = mood_value
            self.current_journal_entry.mood_id = mood_id
            
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
            
            # self.current_journal_entry.notes = notes_value

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Add a note by replying to this message or click No notes",
                reply_markup=reply_markup
            )

        elif data_type == 'no_notes':
            # Final flow: end the conversation
            print(self.current_journal_entry)
            
            
            await self.finalize_journal_entry()

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
            self.current_journal_entry.notes = text

            # self.db.update_row(self.journal_table, journal_id, {'notes': text})
            await self.finalize_journal_entry()

            # Final flow
            await context.bot.send_message(chat_id=message.chat_id, text="Note added. Journal entry complete.\n\n" + str(self.current_journal_entry))
            # Delete the original "Add a note" message
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.reply_to_message.message_id)
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)

    async def post_journal_entry(self):
        """Posts the current journal entry to the Journiv."""
        print(f"Posting journal entry: {self.current_journal_entry}")
        client = JournivClient()
        
        # Login once (you might want to store credentials in config)
        if client.login():
            # Convert to API format
            if not self.current_journal_entry.notes:
                self.current_journal_entry.notes = f"""
People: {", ".join(self.current_journal_entry.people)}
Notes: No notes
""" 
            entry_data = EntryCreate(
                title=f"Journal Entry - {self.current_journal_entry.date.strftime('%d-%m-%Y')}",
                content=self.current_journal_entry.notes,
                entry_date=(self.current_journal_entry.date - timedelta(days=1)).strftime('%d-%m-%Y'),
                journal_id=client.get_journal_id_by_name(Config.JOURNIV_JOURNAL_NAME),
            )
            entry_response = client.create_entry(entry_data)
            
            # Log mood to the journal entry
            mood_log_data = MoodLogCreate(
                mood_id=self.current_journal_entry.mood_id,
                entry_id=entry_response.id,
            )
            client.log_mood(mood_log_data)

            # Add people as tags to the entry
            for person in self.current_journal_entry.people:
                tag = client.get_tag_by_name(person)
                if tag:
                    client.add_tag_to_entry(entry_response.id, tag.id)
                    logger.info(f"Added tag '{person}' to entry {entry_response.id}")
                else:
                    logger.warning(f"Tag '{person}' not found, skipping")

            logger.info(f"Entry created: {entry_response}")
        else:
            logger.error("Failed to authenticate with external API")

    async def finalize_journal_entry(self):
        """Finalize the journal entry by posting it to the DB and external API."""

        # Post to Journiv
        await self.post_journal_entry()
        # Post to DB
        today_entry = self.db.select_row_by_id(self.journal_table, self.current_journal_entry.id)
        if not today_entry:
            self.db.insert_row(self.journal_table, {
                'id': self.current_journal_entry.id,
                'date': self.current_journal_entry.date.isoformat(),
                'mood': self.current_journal_entry.mood,
                'people': ";".join(self.current_journal_entry.people),
                'notes': self.current_journal_entry.notes
            })

    ###########################################################################
    # Below are functions for syncing journal entries to Journiv
    ###########################################################################

    async def sync_all_entries_to_journiv(self, overwrite: bool = False):
        """Sync all existing journal entries from database to Journiv"""
        client = JournivClient()
        client.login()
        journal_id = client.get_journal_id_by_name(Config.JOURNIV_JOURNAL_NAME)
        
        if not client.login():
            logger.error("Failed to authenticate with Journiv")
            return

        # Get all journal entries from your database
        all_entries = self.db.get_all_rows(self.journal_table)
        logger.info(f"Found {len(all_entries)} entries to sync")
        
        successful_syncs = 0
        failed_syncs = 0
        
        all_journiv_entries = self.journiv_client.get_all_journal_entries(journal_id)

        for entry_tuple in all_entries:
            try:
                # Convert tuple to dictionary - you'll need to know the column order
                # Assuming order: id, date, mood, people, notes
                entry_date = self._parse_date(entry_tuple[1])
                entries_with_date = self.journiv_client.get_entries_by_date(all_journiv_entries, entry_date)

                if entries_with_date and not overwrite:
                    logger.info(f"Entry already exists in Journiv: {entry_date}")
                    continue

                entry_dict = {
                    'id': entry_tuple[0],
                    'date': entry_date,
                    'mood': entry_tuple[2],
                    'people': entry_tuple[3],
                    'notes': entry_tuple[4]
                }
                
                # Convert your database entry to Journiv format
                journiv_entry = self._convert_to_journiv_format(entry_dict, client)
                
                # Create entry in Journiv
                response = client.create_entry(journiv_entry)
                
                if response:
                    successful_syncs += 1
                    logger.info(f"Successfully synced entry {entry_dict['id']} to Journiv")
                else:
                    failed_syncs += 1
                    logger.error(f"Failed to sync entry {entry_dict['id']}")
                    
            except Exception as e:
                failed_syncs += 1
                # Use the tuple index for id instead of dict access
                entry_id = entry_tuple[0] if len(entry_tuple) > 0 else "unknown"
                logger.error(f"Error syncing entry {entry_id}: {e}")
                continue

        logger.info(f"Sync completed: {successful_syncs} successful, {failed_syncs} failed")

    async def sync_people_as_tags_to_journiv(self):
        """Sync people from database entries as tags to existing Journiv entries"""
        def normalize_name(name: str) -> str:
            """Normalize a name by removing punctuation and converting to lowercase"""
            if "flavia" in name:
                return "flavia i."
            elif "marta" in name:
                return "marta k"
            else:
                return name

        client = JournivClient()
        
        if not client.login():
            logger.error("Failed to authenticate with Journiv")
            return

        # Get all journal entries from your database
        all_entries = self.db.get_all_rows(self.journal_table)
        logger.info(f"Found {len(all_entries)} entries to process for people tags")
        
        # Get all Journiv entries
        journal_id = client.get_journal_id_by_name(Config.JOURNIV_JOURNAL_NAME)
        all_journiv_entries = client.get_all_journal_entries(journal_id)
        
        successful_tags = 0
        failed_tags = 0
        skipped_tags = 0

        for entry_tuple in all_entries:
            try:
                # Convert tuple to dictionary
                entry_dict = {
                    'id': entry_tuple[0],
                    'date': self._parse_date(entry_tuple[1]),
                    'mood': entry_tuple[2],
                    'people': entry_tuple[3],
                    'notes': entry_tuple[4]
                }
                
                # Skip if no people
                if not entry_dict['people']:
                    continue
                    
                # Parse people from semicolon-separated string
                people_list = [p.strip() for p in entry_dict['people'].split(';') if p.strip()]
                if len (people_list) == 1 and "," in people_list[0]:
                    people_list = [p.strip() for p in people_list[0].split(",")]
                people_list = [normalize_name(p) for p in people_list]
                if not people_list:
                    continue
                
                # Find corresponding Journiv entry by date
                journiv_entries = client.get_entries_by_date(all_journiv_entries, entry_dict['date'])
                if not journiv_entries:
                    logger.warning(f"No Journiv entry found for date {entry_dict['date']}")
                    continue
                    
                # Use the first entry found for that date
                journiv_entry = journiv_entries[0]
                
                # Check if entry already has tags (optional - you might want to skip if tags exist)
                existing_tags = client.get_entry_tags(journiv_entry.id)  # You'll need to implement this method
                
                # Add each person as a tag
                for person in people_list:
                    try:
                        # Get or create tag for this person
                        tag = client.get_tag_by_name(person)
                        if not tag:
                            logger.warning(f"Tag '{person}' not found, skipping")
                            skipped_tags += 1
                            continue
                        
                        # Check if tag already exists on entry (optional)
                        if existing_tags and any(t.id == tag.id for t in existing_tags):
                            logger.info(f"Tag '{person}' already exists on entry {journiv_entry.id}")
                            continue
                        
                        # Add tag to entry
                        client.add_tag_to_entry(journiv_entry.id, tag.id)
                        successful_tags += 1
                        logger.info(f"Added tag '{person}' to entry {journiv_entry.id}")
                        
                    except Exception as e:
                        failed_tags += 1
                        logger.error(f"Error adding tag '{person}' to entry {journiv_entry.id}: {e}")
                        continue
                        
            except Exception as e:
                entry_id = entry_tuple[0] if len(entry_tuple) > 0 else "unknown"
                logger.error(f"Error processing entry {entry_id} for people tags: {e}")
                continue

        logger.info(f"People tags sync completed: {successful_tags} added, {skipped_tags} skipped, {failed_tags} failed")

    def _convert_to_journiv_format(self, db_entry: dict, client: JournivClient) -> EntryCreate:
        """Convert database entry to Journiv EntryCreate format"""
        # Parse the date from your database format
        # entry_date = self._parse_date(db_entry['date'])
        
        # Parse people from semicolon-separated string to list
        people_str = db_entry.get('people', '')
        if people_str:
            people_list = [p.strip() for p in people_str.split(';') if p.strip()]
            people_display = ", ".join(people_list)
        else:
            people_display = "None"
        
        notes = db_entry.get('notes', '') or 'No notes'
        
        content = f"""Mood: {db_entry.get('mood', 0)}/5
    People: {people_display}
    Notes: {notes}"""
        
        # Get journal ID from client or use config fallback
        journal_id = client.get_journal_id_by_name(Config.JOURNIV_JOURNAL_NAME)
        
        return EntryCreate(
            title=f"Journal Entry - {db_entry['date']}",
            content=content,
            entry_date=db_entry['date'],
            journal_id=journal_id
        )

    def _parse_date(self, date_value) -> str:
        """Parse date from various formats to YYYY-MM-DD"""
        try:
            if isinstance(date_value, date):  # Use date directly, not datetime.date
                # Handle datetime.date objects directly
                return date_value.strftime("%Y-%m-%d")
            elif isinstance(date_value, datetime):
                # Handle datetime objects
                return date_value.strftime("%Y-%m-%d")
            elif isinstance(date_value, str):
                # Handle string dates
                if 'T' in date_value:
                    # ISO format: "2024-11-04T19:24:22.618Z"
                    date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                    return date_obj.strftime("%Y-%m-%d")
                else:
                    # Assume it's already in YYYY-MM-DD format
                    return date_value
            else:
                # Fallback for any other type
                return datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Error parsing date {date_value}: {e}")
            # Fallback to today's date
            return datetime.now().strftime("%Y-%m-%d")

        

if __name__ == "__main__":
    import asyncio
    journal = Journal(PostgresDB(
        db_name=Config.POSTGRES_DB_NAME,
        user=Config.POSTGRES_DB_USER,
        password=Config.POSTGRES_DB_PASSWORD,
        host=Config.POSTGRES_DB_HOST,
        port=Config.POSTGRES_DB_PORT
    ))
    asyncio.run(journal.sync_people_as_tags_to_journiv())