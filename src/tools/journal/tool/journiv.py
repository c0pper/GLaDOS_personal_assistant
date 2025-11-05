from datetime import datetime, timedelta
from src.tools.journal.tool.shared_schemas import EntryCreate, EntryResponse, Mood, MoodLogCreate, MoodLogResponse, MoodLogUpdate
from src.config import Config
import requests
from typing import List, Optional
from src.logger import logger
from random import choice

    
class JournivClient:
    MOOD_MAPPING = {
        # 1 - Worst
        "Angry": 1,
        "Anxious": 1,
        "Stressed": 1,
        
        # 2 - Bad
        "Disappointed": 2,
        "Sad": 2,
        "Lonely": 2,
        "Tired": 2,
        
        # 3 - Neutral
        "Confused": 3,
        "Curious": 3,
        "Neutral": 3,
        "Surprised": 3,
        
        # 4 - Good
        "Calm": 4,
        "Relaxed": 4,
        "Focused": 4,
        "Grateful": 4,
        
        # 5 - Best
        "Happy": 5,
        "Excited": 5,
        "Hopeful": 5,
        "Motivated": 5,
        "Proud": 5
    }
    def __init__(self):
        self.base_url = Config.JOURNIV_BASE_URL
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self._journals_cache: Optional[dict] = None

    def login(self) -> bool:
        """Login and store tokens"""
        url = f"{self.base_url}/api/v1/auth/login"

        payload = {"email": Config.JOURNIV_EMAIL, "password": Config.JOURNIV_PASSWORD}
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            logger.info("Logged in to Journiv")
            return True
        logger.error("Failed to log in to Journiv")
        return False

    def refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            return False
            
        url = f"{self.base_url}/api/v1/auth/refresh"
        payload = {"refresh_token": self.refresh_token}
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            return True
        return False

    def _get_headers(self) -> dict:
        """Get headers with auth token"""
        if not self.access_token:
            raise ValueError("Not authenticated. Call login() first.")
        return {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }

    def get_journal_id_by_name(self, journal_name: str) -> Optional[str]:
        """Get journal ID by name"""
        if self._journals_cache is None:
            self._refresh_journals_cache()
        
        return self._journals_cache.get(journal_name.lower())

    def _refresh_journals_cache(self):
        """Refresh the journals cache"""
        url = f"{self.base_url}/api/v1/journals/"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            journals = response.json()
            self._journals_cache = {journal['title'].lower(): journal['id'] for journal in journals}
        else:
            self._journals_cache = {}

    def get_journals(self, include_archived: bool = False):
        """Example API call - get journals"""
        url = f"{self.base_url}/api/v1/journals/"
        params = {"include_archived": str(include_archived).lower()}
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        return response.json()

    def create_journal(self, journal_data: dict):
        """Example API call - create journal entry"""
        url = f"{self.base_url}/api/v1/journals/"
        response = requests.post(url, headers=self._get_headers(), json=journal_data)
        return response.json()

    def create_entry(self, entry_data: EntryCreate) -> EntryResponse:
        """Create a new journal entry"""
        url = f"{self.base_url}/api/v1/entries/"
        entry_data_json = entry_data.model_dump(exclude_unset=True)

        # Convert date format from DD-MM-YYYY to YYYY-MM-DD
        if 'entry_date' in entry_data_json:
            try:
                # Parse DD-MM-YYYY and convert to YYYY-MM-DD
                date_obj = datetime.strptime(entry_data_json['entry_date'], "%d-%m-%Y")
                # Add one day
                date_obj = date_obj + timedelta(days=1)
                entry_data_json['entry_date'] = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                # If it's already in correct format, add one day to that
                try:
                    date_obj = datetime.strptime(entry_data_json['entry_date'], "%Y-%m-%d")
                    date_obj = date_obj + timedelta(days=1)
                    entry_data_json['entry_date'] = date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    # If still can't parse, use today + 1 day as fallback
                    date_obj = datetime.now() + timedelta(days=1)
                    entry_data_json['entry_date'] = date_obj.strftime("%Y-%m-%d")


        response = requests.post(url, headers=self._get_headers(), json=entry_data_json)
        
        if response.status_code == 201:
            return EntryResponse(**response.json())
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.post(url, headers=self._get_headers(), json=entry_data.model_dump(exclude_none=True))
                if response.status_code == 201:
                    return EntryResponse(**response.json())
        
        response.raise_for_status()

    def get_journal_entries(self, journal_id: str, limit: int = 50, offset: int = 0, include_pinned: bool = True) -> List[EntryResponse]:
        """Get entries for a specific journal"""
        url = f"{self.base_url}/api/v1/entries/journal/{journal_id}"
        
        params = {
            'limit': min(limit, 100),  # API limits to 100 max
            'offset': offset,
            'include_pinned': str(include_pinned).lower()
        }
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            entries_data = response.json()
            return [EntryResponse(**entry) for entry in entries_data]
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.get(url, headers=self._get_headers(), params=params)
                if response.status_code == 200:
                    entries_data = response.json()
                    return [EntryResponse(**entry) for entry in entries_data]
        
        response.raise_for_status()
        return []

    def get_all_journal_entries(self, journal_id: str) -> List[EntryResponse]:
        """Get all entries for a journal (handles pagination)"""
        all_entries = []
        limit = 100  # Max per request
        offset = 0
        
        while True:
            entries = self.get_journal_entries(journal_id, limit=limit, offset=offset)
            if not entries:
                break
                
            all_entries.extend(entries)
            
            # If we got fewer than the limit, we've reached the end
            if len(entries) < limit:
                break
                
            offset += limit
        
        return all_entries

    def get_entries_by_date(self, entries: List[EntryResponse], target_date: str) -> List[EntryResponse]:
        """Get all entries for a specific date (YYYY-MM-DD format) from a given list"""
        # Filter entries by date
        matching_entries = []
        for entry in entries:
            if entry.entry_date == target_date:
                matching_entries.append(entry)
        
        return matching_entries

    def get_entries_by_date_range(self, entries: List[EntryResponse], start_date: str, end_date: str) -> List[EntryResponse]:
        """Get all entries within a date range (YYYY-MM-DD format) from a given list"""
        # Filter entries by date range
        matching_entries = []
        for entry in entries:
            if start_date <= entry.entry_date <= end_date:
                matching_entries.append(entry)
        
        return matching_entries
    
    ###########################################################################
    # Moods
    ###########################################################################

    def get_moods(self, category: Optional[str] = None) -> List[Mood]:
        """Get all system moods, optionally filtered by category"""
        url = f"{self.base_url}/api/v1/moods/"
        
        params = {}
        if category:
            params['category'] = category
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            moods_data = response.json()
            return [Mood(**mood) for mood in moods_data]
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.get(url, headers=self._get_headers(), params=params)
                if response.status_code == 200:
                    moods_data = response.json()
                    return [Mood(**mood) for mood in moods_data]
        
        response.raise_for_status()
        return []

    @classmethod
    def convert_mood_to_numeric(cls, mood_name: str) -> int:
        """Convert mood name to 1-5 numeric scale"""
        return cls.MOOD_MAPPING.get(mood_name, 3)  # Default to neutral (3)
    
    @classmethod
    def convert_numeric_to_mood(cls, numeric_mood: int) -> str:
        """Convert numeric mood to possible mood names"""
        return choice([mood for mood, value in cls.MOOD_MAPPING.items() if value == numeric_mood])
    
    def get_mood_logs(self, entry_id: Optional[str] = None, mood_id: Optional[str] = None, 
                     start_date: Optional[str] = None, end_date: Optional[str] = None,
                     limit: int = 50, offset: int = 0) -> List[MoodLogResponse]:
        """Get mood logs for the current user with optional filters"""
        url = f"{self.base_url}/api/v1/moods/logs"
        
        params = {
            'limit': min(limit, 100),
            'offset': offset
        }
        
        if entry_id:
            params['entry_id'] = entry_id
        if mood_id:
            params['mood_id'] = mood_id
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            logs_data = response.json()
            return [MoodLogResponse(**log) for log in logs_data]
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.get(url, headers=self._get_headers(), params=params)
                if response.status_code == 200:
                    logs_data = response.json()
                    return [MoodLogResponse(**log) for log in logs_data]
        
        response.raise_for_status()
        return []

    def entry_has_mood_log(self, entry_id: str) -> bool:
        """Check if an entry already has a mood logged to it"""
        mood_logs = self.get_mood_logs(entry_id=entry_id, limit=1)
        return len(mood_logs) > 0
    
    def log_mood(self, mood_log_data: MoodLogCreate) -> MoodLogResponse:
        """Log a mood for the current user"""
        url = f"{self.base_url}/api/v1/moods/log"
        
        response = requests.post(url, headers=self._get_headers(), json=mood_log_data.model_dump(exclude_unset=True))
        
        if response.status_code == 201:
            return MoodLogResponse(**response.json())
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.post(url, headers=self._get_headers(), json=mood_log_data.model_dump(exclude_unset=True))
                if response.status_code == 201:
                    return MoodLogResponse(**response.json())
        
        response.raise_for_status()
        
    def update_mood_log(self, mood_log_id: str, update_data: MoodLogUpdate) -> MoodLogResponse:
        """Update a mood log"""
        url = f"{self.base_url}/api/v1/moods/log/{mood_log_id}"
        
        response = requests.put(url, headers=self._get_headers(), json=update_data.model_dump(exclude_unset=True))
        
        if response.status_code == 200:
            return MoodLogResponse(**response.json())
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.put(url, headers=self._get_headers(), json=update_data.model_dump(exclude_unset=True))
                if response.status_code == 200:
                    return MoodLogResponse(**response.json())
        
        response.raise_for_status()

    def update_entries_with_moods(self, journal_id: str):
        """Get all journiv entries and update them with moods based on numeric mood in content"""
        # Get all entries
        all_entries = self.get_all_journal_entries(journal_id)
        
        # Get all available moods
        all_moods = self.get_moods()
        mood_name_to_id = {mood.name: mood.id for mood in all_moods}
        
        updated_count = 0
        created_count = 0
        
        for entry in all_entries:
            try:
                # Extract numeric mood from content
                numeric_mood = self._extract_numeric_mood(entry.content)
                if numeric_mood is not None:
                    # Convert numeric mood to mood name
                    mood_name = self.convert_numeric_to_mood(numeric_mood)
                    mood_id = mood_name_to_id.get(mood_name)
                        
                    if mood_id:
                        # Check if entry already has a mood log
                        existing_logs = self.get_mood_logs(entry_id=entry.id, limit=1)
                        
                        if existing_logs:
                            # Update existing mood log
                            existing_log = existing_logs[0]
                            update_data = MoodLogUpdate(
                                mood_id=mood_id,
                                # note=f"Auto-updated from numeric mood {numeric_mood}/5"
                            )
                            self.update_mood_log(existing_log.id, update_data)
                            updated_count += 1
                            logger.info(f"Updated existing mood log for entry {entry.id} with mood {mood_name}")
                        else:
                            # Create new mood log
                            mood_log_data = MoodLogCreate(
                                mood_id=mood_id,
                                # note=f"Auto-migrated from numeric mood {numeric_mood}/5",
                                entry_id=entry.id
                            )
                            self.log_mood(mood_log_data)
                            created_count += 1
                            logger.info(f"Created new mood log for entry {entry.id} with mood {mood_name}")
                    else:
                        logger.warning(f"Mood '{mood_name}' not found in available moods")
                else:
                    logger.info(f"No numeric mood found in entry {entry.id}")
                    
            except Exception as e:
                logger.error(f"Error processing mood for entry {entry.id}: {e}")
                continue
        
        logger.info(f"Mood processing completed: {created_count} created, {updated_count} updated")

    def _extract_numeric_mood(self, content: str) -> Optional[int]:
        """Extract numeric mood from content string"""
        import re
        
        # Look for patterns like "Mood: 1/5", "Mood: 3/5", etc.
        patterns = [
            r"Mood:\s*(\d)/5",
            r"Mood:\s*(\d)/5",
            r"mood:\s*(\d)/5",
            r"Mood\s*(\d)/5"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None

if __name__ == "__main__":
    client = JournivClient()
    client.login()
    # Get all moods
    client.update_entries_with_moods(client.get_journal_id_by_name(Config.JOURNIV_JOURNAL_NAME))