from datetime import datetime
from src.tools.journal.tool.shared_schemas import EntryCreate, EntryResponse
from src.config import Config
import requests
from typing import Optional

    
class JournivClient:
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
            return True
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
                entry_data_json['entry_date'] = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                # If it's already in correct format, leave it as is
                pass

        response = requests.post(url, headers=self._get_headers(), json=entry_data_json)
        
        if response.status_code == 201:
            return EntryResponse(**response.json())
        elif response.status_code == 401:
            if self.refresh_access_token():
                response = requests.post(url, headers=self._get_headers(), json=entry_data.model_dump(exclude_none=True))
                if response.status_code == 201:
                    return EntryResponse(**response.json())
        
        response.raise_for_status()
    

if __name__ == "__main__":
    client = JournivClient()
    client.login()
    journals = client.get_journals()
    print(journals)