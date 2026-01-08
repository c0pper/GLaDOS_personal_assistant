
import time
from typing import List
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ContextTypes
from src.config import Config
import requests
import json
from atomic_agents import AgentConfig, AtomicAgent, BaseIOSchema
from src.agents.pii_identifier_agent import PersonalInfoIdentifierInputSchema, PersonalInfoIdentifierOutputSchema, personal_info_identifier_config, PersonalInfoIdentifierAgent
from src.agents.pii_report_writer import UserProfileAnalyzerInputSchema, UserProfileAnalyzer, user_profile_analyzer_config
from src.logger import logger


class RedditUserSearch:
    """
    Searches for a user on Reddit.
    """
    def __init__(self, context: ContextTypes.DEFAULT_TYPE = None):
        self.pii_identifier = PersonalInfoIdentifierAgent(config=personal_info_identifier_config)
        self.bot_context = context
        self.status_message_id = None


    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the initial /search_reddit_user command."""
        self.bot_context = context
        chat_id = Config.MY_CHAT_ID
        text = " ".join(context.args)
        if not text:
            await context.bot.send_message(chat_id=chat_id, text="Please provide a username to search for.")
            return
        result = await self.run_search(text)
        
        await self.bot_context.bot.edit_message_text(
            text=result,
            chat_id=chat_id,
            message_id=self.status_message_id,
        )
        # await context.bot.send_message(chat_id=chat_id, text=result)


    async def get_relevant_comments(self, username: str, limit: int = 1000) -> set:
        """
        Fetches all comments from a user's Reddit profile.

        Args:
            username (str): The username to search for.
            limit (int, optional): The maximum number of comments to fetch. Defaults to 1000.

        Returns:
            set: A set of all comments.
        """
        logger.info(f"Fetching comments for user: {username}")
        all_comments = []
        relevant_comments = set()
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

        status = await self.bot_context.bot.send_message(chat_id=Config.MY_CHAT_ID, text=f"Fetching comments for user: {username}")
        self.status_message_id = status.message_id

        while True:
            if len(all_comments) >= limit:
                logger.info(f"Reached limit of {limit} comments.")
                break
            
            logger.info(f"Fetching page {page}...")
                        
            try:
                # response = requests.get(base_url, headers=headers, params=querystring)
                response = requests.get(f"https://pay.reddit.com/user/{username}/comments.json?t=all&t=all&limit=100&sort=new&jsonp=_jqjsp&callback=_jqjsp&_1763913889807&after{after_param}", headers=headers)
                
                # Remove JSONP wrapper to get pure JSON
                if response.text.startswith('/**/_jqjsp('):
                    text = response.text.replace("/**/_jqjsp(", "")[:-1]

                    
                    json_result = json.loads(text)
                    
                    # Extract comments from this page
                    comments = json_result.get('data', {}).get('children', [])
                    if not comments:
                        logger.info("No more comments found.")
                        await self.bot_context.bot.edit_message_text(
                            text=f"Fetching comments for user: {username}\nNo more comments found.",
                            chat_id=Config.MY_CHAT_ID,
                            message_id=status.message_id,
                        )
                        break
                        
                    all_comments.extend(comments)
                    comments_bodies = set([comm['data']['body'] for comm in comments])
                    pii_comments = await self.filter_pii_comments(comments_bodies)
                    relevant_comments.update(pii_comments)
                    logger.info(f"Page {page}: Got {len(comments)} comments (Total comments: {len(all_comments)}, Total relevant: {len(relevant_comments)})")
                    await self.bot_context.bot.edit_message_text(
                        text=f"Fetching comments for user: {username}\nPage {page}: Got {len(comments)} comments (Total comments: {len(all_comments)}, Total relevant: {len(relevant_comments)})",
                        chat_id=Config.MY_CHAT_ID,
                        message_id=status.message_id,
                    )
                    
                    # Get the after parameter for next page
                    after_param = f"={json_result.get('data', {}).get('after')}"
                    if not after_param:
                        logger.info("No more pages available.")
                        await self.bot_context.bot.edit_message_text(
                            text=f"Fetching comments for user: {username}\nNo more pages available.",
                            chat_id=Config.MY_CHAT_ID,
                            message_id=status.message_id,
                        )
                        break

                page += 1
                
                # Be nice to the API - add a small delay
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        return relevant_comments
    

    async def filter_pii_comments(self, comments: set) -> set:
        """
        Extracts personal information from a user's Reddit profile.
        
        Args:
            username (str): The username to search for.
        
        Returns:
            list: A list of personal information items.
        """
        comments = await self.filter_long_comments(comments)
        comments = list(comments)
        pii_items = []

        numbered_comments = "\n".join([f"{i}: {comment}" for i, comment in enumerate(comments)])
        self.pii_identifier.agent.reset_history()
        analysis_result: PersonalInfoIdentifierOutputSchema = self.pii_identifier.agent.run(
            PersonalInfoIdentifierInputSchema(
                user_messages=numbered_comments
            )
        )
        for item in analysis_result.items_found_indexes:
            try:
                pii_items.append(comments[item])
            except IndexError:
                logger.error(f"Index {item} out of range for comments: {comments}")
        
        return pii_items

    async def filter_long_comments(self, comments: set, char_limit: int = 3000) -> set:
        return {comment for comment in comments if len(comment) <= char_limit}
    
    async def get_user_profile_analysis(self, comments: List[str]) -> str:
        """
        Runs the user profile analysis on the provided comments.
        
        Args:
            comments (List[str]): The comments to analyze.
            
        Returns:
            str: The analysis report in Markdown format.
        """
        logger.info(f"Running user profile analysis on {len(comments)} comments")
        await self.bot_context.bot.edit_message_text(
            text=f"Running user profile analysis on {len(comments)} comments...",
            chat_id=Config.MY_CHAT_ID,
            message_id=self.status_message_id,
        )
        user_messages = UserProfileAnalyzerInputSchema(relevant_comments=comments)
        analyzer = UserProfileAnalyzer(config=user_profile_analyzer_config)
        return analyzer.run_and_generate_markdown_report(user_messages)
    
    async def run_search(self, username: str) -> str:
        """
        Runs the search for a user on Reddit and returns the analysis report.
        
        Args:
            username (str): The username to search for.
            
        Returns:
            str: The analysis report in Markdown format.
        """
        message = await self.bot_context.bot.send_message(chat_id=Config.MY_CHAT_ID, text=f"Searching for user: {username}")
        logger.info(f"Searching for user: {username}")
        comments = await self.get_relevant_comments(username, limit=2000)
        if len(comments) == 0:
            return "No relevant comments found."
        report = await self.get_user_profile_analysis(comments)
        return report

if __name__ == "__main__":
    import asyncio
    reddit = RedditUserSearch()
    report = asyncio.run(reddit.run_search("Swivials "))
    print(report)