
import time
from telegram import Update
from telegram.ext import ContextTypes
from src.config import Config
import requests
import json


class RedditUserSearch:
    """
    Searches for a user on Reddit.
    """
    def __init__(self):
        pass


    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the initial /search_reddit_user command."""
        chat_id = Config.MY_CHAT_ID
        text = " ".join(context.args)
        result = await self.search_user(text)
        
        await context.bot.send_message(chat_id=chat_id, text=result)

    async def search_user(self, username):
        """
        Searches for a user on Reddit and returns their profile information.

        Args:
            username (str): The username to search for.

        Returns:
            dict: The user's profile information.
        """
        return username

    async def get_all_comments(self, username):
        base_url = f"https://pay.reddit.com/user/{username}/comments/"
        all_comments = []
        all_comments_bodies = set()
        after_param = ""  # Start with empty after parameter
        
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.5",
            "connection": "keep-alive",
            "host": "pay.reddit.com",
            "referer": "https://redditcommentsearch.com/",
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0"
        }
        
        page = 1
        while True:
            print(f"Fetching page {page}...")
            
            # Build querystring with current after parameter
            querystring = {
                "t": "all",
                "limit": "100",
                "sort": "new",
                "jsonp": "_jqjsp",
                "callback": "_jqjsp",
                "after": after_param,
                "_": str(int(time.time() * 1000))  # Current timestamp for cache busting
            }
            
            try:
                response = requests.get(base_url, headers=headers, params=querystring)
                
                # Remove JSONP wrapper to get pure JSON
                if response.text.startswith('/**/_jqjsp('):
                    text = response.text.replace("/**/_jqjsp(", "")[:-1]
                else:
                    text = response.text
                    
                json_result = json.loads(text)
                
                # Extract comments from this page
                comments = json_result.get('data', {}).get('children', [])
                if not comments:
                    print("No more comments found.")
                    break
                    
                all_comments.extend(comments)
                comments_bodies = set([comm['data']['body'] for comm in comments])
                all_comments_bodies.update(comments_bodies)
                print(f"Page {page}: Got {len(comments)} comments (Total: {len(all_comments)})")
                
                # Get the after parameter for next page
                after_param = json_result.get('data', {}).get('after')
                if not after_param:
                    print("No more pages available.")
                    break
                    
                page += 1
                
                # Be nice to the API - add a small delay
                time.sleep(1)
                
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
        
        return all_comments_bodies

if __name__ == "__main__":
    import asyncio
    reddit = RedditUserSearch()
    comments = asyncio.run(reddit.get_all_comments())
    print(comments)