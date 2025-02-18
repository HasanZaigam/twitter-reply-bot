import tweepy
from airtable import Airtable
from datetime import datetime, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
import schedule
import time
import os

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Twitter API keys from environment variables
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Airtable API keys
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_KEY = os.getenv("AIRTABLE_BASE_KEY")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class TwitterBot:
    def __init__(self):
        self.twitter_api = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )

        self.airtable = Airtable(AIRTABLE_BASE_KEY, AIRTABLE_TABLE_NAME, AIRTABLE_API_KEY)
        self.twitter_me_id = self.get_me_id()
        self.tweet_response_limit = 35  # Max tweets to respond to per run

        # Initialize the LLM (Using Gemini API)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.6
        )

        # Stats tracking
        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0

    def generate_response(self, mentioned_conversation_tweet_text):
        """Generates a Web3-focused response for a tweet mention."""
        system_template = """
            You are OperateCrypto AI, a Web3 futurist and crypto analyst.
            Your goal is to provide **concise, engaging, and insightful** responses about blockchain, DeFi, DAOs, and decentralization.

            % RESPONSE TONE:
            - Direct, **slightly mysterious**, and **future-focused**.
            - No fluff. Straight to the point.
            - Occasionally witty, but always **authoritative**.

            % RESPONSE FORMAT:
            - Keep it **under 200 characters**.
            - **One or two sentences max**.
            - No emojis.
            
            % RESPONSE CONTENT:
            - If the tweet is about **decentralization, DAOs, crypto regulation, or DeFi**, provide an **insightful take**.
            - If asked about **the future**, make a **bold but realistic prediction**.
            - If a tweet lacks context, reply: **"Crypto never sleeps, but I need more details."**
        """
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_message_prompt = HumanMessagePromptTemplate.from_template("{text}")
        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])

        final_prompt = chat_prompt.format_prompt(text=mentioned_conversation_tweet_text).to_messages()
        response = self.llm.invoke(final_prompt).content  # Invoke Gemini API

        return response

    def respond_to_mention(self, mention, mentioned_conversation_tweet):
        """Replies to a mention with an AI-generated response."""
        response_text = self.generate_response(mentioned_conversation_tweet.text)
        
        try:
            response_tweet = self.twitter_api.create_tweet(
                text=response_text, 
                in_reply_to_tweet_id=mention.id
            )
            self.mentions_replied += 1
        except Exception as e:
            print(e)
            self.mentions_replied_errors += 1
            return
        
        # Log in Airtable
        self.airtable.insert({
            "mentioned_conversation_tweet_id": str(mentioned_conversation_tweet.id),
            "mentioned_conversation_tweet_text": mentioned_conversation_tweet.text,
            "tweet_response_id": response_tweet.data["id"],
            "tweet_response_text": response_text,
            "tweet_response_created_at": datetime.utcnow().isoformat(),
            "mentioned_at": mention.created_at.isoformat(),
        })
        return True

    def get_me_id(self):
        """Returns the authenticated Twitter account's user ID."""
        return self.twitter_api.get_me()[0].id

    def get_mention_conversation_tweet(self, mention):
        """Retrieves the parent tweet of a mention (if it exists)."""
        if mention.conversation_id is not None:
            conversation_tweet = self.twitter_api.get_tweet(mention.conversation_id).data
            return conversation_tweet
        return None

    def get_mentions(self):
        """Fetches recent mentions of the bot within the last 20 minutes."""
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        return self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time_str,
            expansions=["referenced_tweets.id"],
            tweet_fields=["created_at", "conversation_id"]
        ).data

    def check_already_responded(self, mentioned_conversation_tweet_id):
        """Checks Airtable to see if the bot has already replied to a mention."""
        records = self.airtable.get_all(view="Grid view")
        for record in records:
            if record["fields"].get("mentioned_conversation_tweet_id") == str(mentioned_conversation_tweet_id):
                return True
        return False

    def respond_to_mentions(self):
        """Processes and replies to new mentions."""
        mentions = self.get_mentions()

        if not mentions:
            print("No mentions found.")
            return
        
        self.mentions_found = len(mentions)

        for mention in mentions[:self.tweet_response_limit]:
            mentioned_conversation_tweet = self.get_mention_conversation_tweet(mention)

            if (mentioned_conversation_tweet.id != mention.id
                and not self.check_already_responded(mentioned_conversation_tweet.id)):
                self.respond_to_mention(mention, mentioned_conversation_tweet)
        return True

    def execute_replies(self):
        """Executes the bot's response function with logging."""
        print(f"Starting Job: {datetime.utcnow().isoformat()}")
        self.respond_to_mentions()
        print(f"Finished Job: {datetime.utcnow().isoformat()}, Found: {self.mentions_found}, Replied: {self.mentions_replied}, Errors: {self.mentions_replied_errors}")

# Schedules the bot to run every 6 minutes
def job():
    print(f"Job executed at {datetime.utcnow().isoformat()}")
    bot = TwitterBot()
    bot.execute_replies()

if __name__ == "__main__":
    schedule.every(6).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
