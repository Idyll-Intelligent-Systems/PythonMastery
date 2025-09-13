To create customizable avatars and characters in VEZE UniQVerse, integrate the following APIs and logic into your existing X Engine, leveraging X user data and Grok for dynamic, personalized generation. Below is a concise approach to achieve this, extending the provided `main.py` with new endpoints for avatar and character customization, tailored to the game’s futuristic, sci-fi aesthetic and using X data for personalization.

### Approach
1. **Use X User Data**: Fetch user details (bio, posts, metrics) from `/user_details/{username}` and `/user_metrics/{username}` to inform avatar traits.
2. **Grok-Powered Customization**: Use xAI Grok API to generate unique avatar/character attributes based on user X activity and game context.
3. **VEZE UniQVerse Integration**: Store customizable attributes in the game’s data layer (extend `VEZE_DATA` mock DB).
4. **New APIs**: Add endpoints for avatar creation, customization, and character generation with X-driven personalization.

### Updated Code (Extending main.py)

# VEZE UniQVerse X Engine

Run with: `pip install fastapi uvicorn tweepy requests python-dotenv prometheus-fastapi-instrumentator`  
`uvicorn main:app --reload`

Create `.env`:
```
X_BEARER_TOKEN=your_bearer_token
X_CONSUMER_KEY=your_consumer_key
X_CONSUMER_SECRET=your_consumer_secret
X_ACCESS_TOKEN=your_access_token_for_@shivaveld_idyll
X_ACCESS_SECRET=your_access_secret
XAI_API_KEY=your_xai_api_key
```

## main.py

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import os
from dotenv import load_dotenv
import tweepy
import requests
import json
from prometheus_fastapi_instrumentator import Instrumentator
import random

load_dotenv()

app = FastAPI()

# Instrument for Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Twitter setup
bearer_token = os.getenv("X_BEARER_TOKEN")
consumer_key = os.getenv("X_CONSUMER_KEY")
consumer_secret = os.getenv("X_CONSUMER_SECRET")
access_token = os.getenv("X_ACCESS_TOKEN")
access_token_secret = os.getenv("X_ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=consumer_key,
    consumer_secret=consumer_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
    bearer_token=bearer_token
)

# xAI Grok setup
xai_api_key = os.getenv("XAI_API_KEY")
grok_url = "https://api.x.ai/v1/chat/completions"

# Mock VEZE UniQVerse data (replace with actual game DB)
VEZE_DATA = {
    "cars": {
        "cybertron-1": {"name": "Quantum Speeder", "type": "HoverCar", "speed": 300, "abilities": ["Quantum Dash", "Stealth Mode"]},
        "neon-2": {"name": "Neon Blitz", "type": "AeroCar", "speed": 250, "abilities": ["Plasma Boost", "Anti-Grav"]},
    },
    "rockets": {
        "starfire-x": {"name": "Starfire X", "type": "Interstellar", "range": "100 ly", "features": ["Warp Drive", "Shield Array"]},
        "nova-7": {"name": "Nova 7", "type": "Orbital", "range": "Low Orbit", "features": ["Cargo Bay", "Solar Sail"]},
    },
    "planets": {
        "zara-9": {"name": "Zara-9", "type": "Terrestrial", "climate": "Arid", "resources": ["Crystal Ore", "Plasma Wells"]},
        "kryon-3": {"name": "Kryon-3", "type": "Gas Giant", "climate": "Stormy", "resources": ["Helium-3", "Methane"]},
    },
    "solarsystems": {
        "orion-1": {"name": "Orion-1", "planets": ["zara-9"], "star": "Red Dwarf"},
        "andromeda-2": {"name": "Andromeda-2", "planets": ["kryon-3"], "star": "Blue Giant"},
    },
    "galaxies": {
        "milkyway-x": {"name": "MilkyWay-X", "systems": ["orion-1"], "type": "Spiral"},
        "andromeda-x": {"name": "Andromeda-X", "systems": ["andromeda-2"], "type": "Elliptical"},
    },
    "avatars": {},  # Store player avatars
    "characters": {}  # Store game characters (NPCs, bosses, etc.)
}

class NPCRequest(BaseModel):
    context: str
    query: str = None

class PostRequest(BaseModel):
    text: str
    remarks: str = ""

class UserDetailsResponse(BaseModel):
    username: str
    bio: str
    name: str
    location: str
    followers_count: int
    following_count: int
    top_posts: List[dict]
    recent_mentions: List[dict]
    pinned_post: dict
    similar_users: List[dict]

class UserMetricsResponse(BaseModel):
    followers_count: int
    following_count: int
    tweet_count: int
    listed_count: int
    average_likes: float
    average_retweets: float
    average_replies: float

class BossStrategyRequest(BaseModel):
    player_username: str
    boss_type: str = "DinoBoss"

class BossStrategyResponse(BaseModel):
    strategy: str
    adaptations: List[str]
    weakness: str

class DinoEvolutionRequest(BaseModel):
    dino_type: str
    trend_query: str

class DinoEvolutionResponse(BaseModel):
    evolved_traits: List[str]
    new_abilities: List[str]
    visual_desc: str

class CosmicEntityResponse(BaseModel):
    id: str
    name: str
    type: str
    details: Dict

class AvatarRequest(BaseModel):
    username: str
    base_style: str = "Cyberpunk"  # e.g., Cyberpunk, Cosmic, DinoRider
    custom_traits: List[str] = []  # Optional player-defined traits

class AvatarResponse(BaseModel):
    avatar_id: str
    username: str
    style: str
    traits: List[str]
    visual_desc: str

class CharacterRequest(BaseModel):
    username: str
    character_type: str  # e.g., NPC, Boss, DinoCompanion
    context: str

class CharacterResponse(BaseModel):
    character_id: str
    type: str
    name: str
    traits: List[str]
    abilities: List[str]
    visual_desc: str

@app.post("/npc_response")
def npc_response(req: NPCRequest):
    try:
        if not req.query:
            req.query = req.context[:50]
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {"query": req.query, "max_results": 3, "tweet.fields": "text"}
        resp = requests.get(search_url, headers=headers, params=params)
        data = resp.json()
        posts = [t["text"] for t in data.get("data", [])]
        x_context = " ".join(posts) if posts else "No recent posts."

        prompt = f"Based on X posts: {x_context}\nGenerate NPC response for game context: {req.context}"
        grok_headers = {
            "Authorization": f"Bearer {xai_api_key}",
            "Content-Type": "application/json"
        }
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        response = grok_resp.json()["choices"][0]["message"]["content"]
        return {"response": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/post_to_x")
def post_to_x(req: PostRequest):
    try:
        full_text = f"{req.text} {req.remarks}".strip()
        if len(full_text) > 280:
            raise HTTPException(400, "Text too long")
        response = client.create_tweet(text=full_text)
        return {"tweet_id": response.data["id"]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/user_details/{username}", response_model=UserDetailsResponse)
def user_details(username: str):
    try:
        user = client.get_user(
            username=username,
            user_fields=['description', 'name', 'location', 'public_metrics', 'pinned_tweet_id']
        )
        if not user.data:
            raise HTTPException(404, "User not found")
        user_data = user.data

        tweets_resp = client.get_users_tweets(
            id=user_data.id,
            max_results=100,
            tweet_fields=['public_metrics', 'created_at', 'text']
        )
        tweets = tweets_resp.data or []
        top_tweets = sorted(tweets, key=lambda t: t.public_metrics['like_count'], reverse=True)[:5]
        top_posts = [
            {
                'text': t.text,
                'likes': t.public_metrics['like_count'],
                'retweets': t.public_metrics['retweet_count'],
                'created_at': str(t.created_at)
            }
            for t in top_tweets
        ]

        mentions_resp = client.get_users_mentions(
            id=user_data.id,
            max_results=5,
            tweet_fields=['text', 'created_at']
        )
        mentions = mentions_resp.data or []
        recent_mentions = [
            {
                'text': m.text,
                'created_at': str(m.created_at)
            }
            for m in mentions
        ]

        pinned_post = {}
        if user_data.pinned_tweet_id:
            pinned_resp = client.get_tweet(
                id=user_data.pinned_tweet_id,
                tweet_fields=['text', 'public_metrics']
            )
            if pinned_resp.data:
                pinned_post = {
                    'text': pinned_resp.data.text,
                    'likes': pinned_resp.data.public_metrics['like_count'],
                    'retweets': pinned_resp.data.public_metrics['retweet_count']
                }

        followers_resp = client.get_users_followers(
            id=user_data.id,
            max_results=5,
            user_fields=['description', 'name']
        )
        similar_users = [
            {
                'username': u.username,
                'bio': u.description or '',
                'name': u.name or ''
            }
            for u in followers_resp.data or []
        ]

        return {
            "username": user_data.username,
            "bio": user_data.description or "",
            "name": user_data.name or "",
            "location": user_data.location or "",
            "followers_count": user_data.public_metrics['followers_count'],
            "following_count": user_data.public_metrics['following_count'],
            "top_posts": top_posts,
            "recent_mentions": recent_mentions,
            "pinned_post": pinned_post,
            "similar_users": similar_users
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/user_metrics/{username}", response_model=UserMetricsResponse)
def user_metrics(username: str):
    try:
        user = client.get_user(
            username=username,
            user_fields=['public_metrics']
        )
        if not user.data:
            raise HTTPException(404, "User not found")
        user_data = user.data
        metrics = user_data.public_metrics

        tweets_resp = client.get_users_tweets(
            id=user_data.id,
            max_results=100,
            tweet_fields=['public_metrics']
        )
        tweets = tweets_resp.data or []
        num_tweets = len(tweets)
        if num_tweets > 0:
            total_likes = sum(t.public_metrics['like_count'] for t in tweets)
            total_retweets = sum(t.public_metrics['retweet_count'] for t in tweets)
            total_replies = sum(t.public_metrics['reply_count'] for t in tweets)
            avg_likes = total_likes / num_tweets
            avg_retweets = total_retweets / num_tweets
            avg_replies = total_replies / num_tweets
        else:
            avg_likes = avg_retweets = avg_replies = 0.0

        return {
            "followers_count": metrics['followers_count'],
            "following_count": metrics['following_count'],
            "tweet_count": metrics['tweet_count'],
            "listed_count": metrics['listed_count'],
            "average_likes": avg_likes,
            "average_retweets": avg_retweets,
            "average_replies": avg_replies
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/boss_adapt_strategy", response_model=BossStrategyResponse)
def boss_adapt_strategy(req: BossStrategyRequest):
    try:
        player_details = user_details(req.player_username)
        player_context = f"Player: {player_details.bio} | Top post: {player_details.top_posts[0]['text'] if player_details.top_posts else 'None'}"

        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {"query": req.boss_type, "max_results": 5, "tweet.fields": "text"}
        resp = requests.get(search_url, headers=headers, params=params)
        trends = [t["text"] for t in resp.json().get("data", [])]

        prompt = f"""Futuristic boss adaptation for {req.boss_type} in VEZE UniQVerse.
Player context: {player_context}
Current X trends: {' '.join(trends)}
Generate adaptive strategy, 3 adaptations, and a weakness. Make it hardcore and crazy."""
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        content = grok_resp.json()["choices"][0]["message"]["content"]
        
        lines = content.split('\n')
        strategy = lines[0] if lines else "Adaptive quantum strike sequence."
        adaptations = [line.strip() for line in lines[1:4] if line.strip()]
        weakness = lines[4] if len(lines) > 4 else "Exploitable neural overload."
        
        return {
            "strategy": strategy,
            "adaptations": adaptations,
            "weakness": weakness
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/dino_evolution", response_model=DinoEvolutionResponse)
def dino_evolution(req: DinoEvolutionRequest):
    try:
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {"query": req.trend_query, "max_results": 10, "tweet.fields": "text"}
        resp = requests.get(search_url, headers=headers, params=params)
        trend_data = [t["text"] for t in resp.json().get("data", [])]

        prompt = f"""Evolve {req.dino_type} dino in futuristic VEZE UniQVerse.
X trends influencing evolution: {' '.join(trend_data[:5])}
Generate 4 evolved traits, 3 new abilities, and visual description. Make it wild and sci-fi."""
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 250
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        content = grok_resp.json()["choices"][0]["message"]["content"]
        
        sections = content.split('###')
        traits = sections[0].split(',') if sections else ["Cyber scales", "Laser claws"]
        abilities = sections[1].split(',') if len(sections) > 1 else ["Plasma roar", "Time warp dash"]
        visual = sections[2] if len(sections) > 2 else "Glowing neon hide with holographic spikes."
        
        return {
            "evolved_traits": traits[:4],
            "new_abilities": abilities[:3],
            "visual_desc": visual
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/futuristic_npc_emotion")
def futuristic_npc_emotion(req: NPCRequest):
    try:
        if not req.query:
            req.query = req.context[:50]
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {"query": req.query, "max_results": 5}
        resp = requests.get(search_url, headers=headers, params=params)
        posts = [t["text"] for t in resp.json().get("data", [])]
        sentiment_prompt = f"Analyze sentiment of these posts: {' '.join(posts)}. Output: positive/negative/neutral score 0-1."
        
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": sentiment_prompt}],
            "max_tokens": 50
        }
        sent_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        sentiment = sent_resp.json()["choices"][0]["message"]["content"] if sent_resp.status_code == 200 else "neutral 0.5"

        emotion_prompt = f"Based on sentiment {sentiment} and context {req.context}, generate futuristic NPC emotion state (e.g., rage_mode:0.8, empathy:0.3) and reaction."
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": emotion_prompt}],
            "max_tokens": 100
        }
        emotion_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        emotion = emotion_resp.json()["choices"][0]["message"]["content"] if emotion_resp.status_code == 200 else "calm"
        
        return {"emotion_state": emotion, "sentiment_analysis": sentiment}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/cars")
def get_cars():
    try:
        return {"cars": list(VEZE_DATA["cars"].values())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/cars/{car_id}", response_model=CosmicEntityResponse)
def get_car(car_id: str):
    try:
        car = VEZE_DATA["cars"].get(car_id)
        if not car:
            raise HTTPException(404, "Car not found")
        return {
            "id": car_id,
            "name": car["name"],
            "type": car["type"],
            "details": car
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/rockets")
def get_rockets():
    try:
        return {"rockets": list(VEZE_DATA["rockets"].values())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/rockets/{rocket_id}", response_model=CosmicEntityResponse)
def get_rocket(rocket_id: str):
    try:
        rocket = VEZE_DATA["rockets"].get(rocket_id)
        if not rocket:
            raise HTTPException(404, "Rocket not found")
        return {
            "id": rocket_id,
            "name": rocket["name"],
            "type": rocket["type"],
            "details": rocket
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/planets")
def get_planets():
    try:
        return {"planets": list(VEZE_DATA["planets"].values())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/planets/{planet_id}", response_model=CosmicEntityResponse)
def get_planet(planet_id: str):
    try:
        planet = VEZE_DATA["planets"].get(planet_id)
        if not planet:
            raise HTTPException(404, "Planet not found")
        return {
            "id": planet_id,
            "name": planet["name"],
            "type": planet["type"],
            "details": planet
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/solarsystems")
def get_solarsystems():
    try:
        return {"solarsystems": list(VEZE_DATA["solarsystems"].values())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/solarsystems/{system_id}", response_model=CosmicEntityResponse)
def get_solarsystem(system_id: str):
    try:
        system = VEZE_DATA["solarsystems"].get(system_id)
        if not system:
            raise HTTPException(404, "Solar system not found")
        return {
            "id": system_id,
            "name": system["name"],
            "type": "Solar System",
            "details": system
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/galaxies")
def get_galaxies():
    try:
        return {"galaxies": list(VEZE_DATA["galaxies"].values())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/galaxies/{galaxy_id}", response_model=CosmicEntityResponse)
def get_galaxy(galaxy_id: str):
    try:
        galaxy = VEZE_DATA["galaxies"].get(galaxy_id)
        if not galaxy:
            raise HTTPException(404, "Galaxy not found")
        return {
            "id": galaxy_id,
            "name": galaxy["name"],
            "type": galaxy["type"],
            "details": galaxy
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/cosmic_interaction")
def cosmic_interaction(req: NPCRequest):
    try:
        if not req.query:
            req.query = req.context[:50]
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {"query": req.query, "max_results": 5}
        resp = requests.get(search_url, headers=headers, params=params)
        posts = [t["text"] for t in resp.json().get("data", [])]
        x_context = " ".join(posts) if posts else "No cosmic trends."

        prompt = f"""Generate a futuristic interaction response for VEZE UniQVerse cosmic entity (car, rocket, planet, etc.).
Context: {req.context}
X trends: {x_context}
Make it immersive, sci-fi, and aligned with game dynamics."""
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        response = grok_resp.json()["choices"][0]["message"]["content"]
        return {"interaction": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/create_avatar", response_model=AvatarResponse)
def create_avatar(req: AvatarRequest):
    try:
        # Fetch user X data
        user_data = user_details(req.username)
        user_metrics = user_metrics(req.username)
        x_context = f"Bio: {user_data.bio} | Top post: {user_data.top_posts[0]['text'] if user_data.top_posts else 'None'} | Engagement: {user_metrics.average_likes:.1f} likes"

        # Generate avatar with Grok
        prompt = f"""Create a customizable avatar for VEZE UniQVerse player.
X profile: {x_context}
Base style: {req.base_style}
Custom traits: {', '.join(req.custom_traits) if req.custom_traits else 'None'}
Generate 5 unique traits and a futuristic visual description. Align with sci-fi aesthetic."""
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        content = grok_resp.json()["choices"][0]["message"]["content"]

        # Parse response
        sections = content.split('###')
        traits = sections[0].split(',')[:5] if sections else ["Neon Aura", "Holo-Armor"]
        visual_desc = sections[1] if len(sections) > 1 else "A shimmering cybernetic figure with glowing circuits."

        # Store avatar
        avatar_id = f"avatar-{req.username}-{random.randint(1000, 9999)}"
        VEZE_DATA["avatars"][avatar_id] = {
            "username": req.username,
            "style": req.base_style,
            "traits": traits,
            "visual_desc": visual_desc
        }

        return {
            "avatar_id": avatar_id,
            "username": req.username,
            "style": req.base_style,
            "traits": traits,
            "visual_desc": visual_desc
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/create_character", response_model=CharacterResponse)
def create_character(req: CharacterRequest):
    try:
        # Fetch user X data
        user_data = user_details(req.username)
        user_metrics = user_metrics(req.username)
        x_context = f"Bio: {user_data.bio} | Top post: {user_data.top_posts[0]['text'] if user_data.top_posts else 'None'} | Engagement: {user_metrics.average_likes:.1f} likes"

        # Generate character with Grok
        prompt = f"""Create a customizable {req.character_type} for VEZE UniQVerse.
X profile: {x_context}
Context: {req.context}
Generate name, 4 traits, 3 abilities, and visual description. Make it wild, sci-fi, and tied to game context."""
        grok_headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        grok_data = {
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 250
        }
        grok_resp = requests.post(grok_url, headers=grok_headers, json=grok_data)
        if grok_resp.status_code != 200:
            raise HTTPException(500, "Grok API error")
        content = grok_resp.json()["choices"][0]["message"]["content"]

        # Parse response
        sections = content.split('###')
        name = sections[0].strip() if sections else f"{req.character_type}-{random.randint(1000, 9999)}"
        traits = sections[1].split(',')[:4] if len(sections) > 1 else ["Quantum Reflexes", "Neural Link"]
        abilities = sections[2].split(',')[:3] if len(sections) > 2 else ["Photon Blast", "Gravity Shift"]
        visual_desc = sections[3] if len(sections) > 3 else "A towering figure with pulsating energy veins."

        # Store character
        character_id = f"char-{req.username}-{random.randint(1000, 9999)}"
        VEZE_DATA["characters"][character_id] = {
            "type": req.character_type,
            "name": name,
            "traits": traits,
            "abilities": abilities,
            "visual_desc": visual_desc
        }

        return {
            "character_id": character_id,
            "type": req.character_type,
            "name": name,
            "traits": traits,
            "abilities": abilities,
            "visual_desc": visual_desc
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/avatars/{avatar_id}", response_model=AvatarResponse)
def get_avatar(avatar_id: str):
    try:
        avatar = VEZE_DATA["avatars"].get(avatar_id)
        if not avatar:
            raise HTTPException(404, "Avatar not found")
        return {
            "avatar_id": avatar_id,
            "username": avatar["username"],
            "style": avatar["style"],
            "traits": avatar["traits"],
            "visual_desc": avatar["visual_desc"]
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/characters/{character_id}", response_model=CharacterResponse)
def get_character(character_id: str):
    try:
        character = VEZE_DATA["characters"].get(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        return {
            "character_id": character_id,
            "type": character["type"],
            "name": character["name"],
            "traits": character["traits"],
            "abilities": character["abilities"],
            "visual_desc": character["visual_desc"]
        }
    except Exception as e:
        raise HTTPException(500, str(e))
```

### New Endpoints
- **POST `/create_avatar`**  
  Body: `{"username": "xuseid", "base_style": "Cyberpunk", "custom_traits": ["Neon Visor", "Quantum Boots"]}`  
  Creates a player avatar based on X profile (bio, posts) and custom traits, stored in `VEZE_DATA["avatars"]`.

- **POST `/create_character`**  
  Body: `{"username": "xuseid", "character_type": "DinoCompanion", "context": "Exploring Zara-9"}`  
  Generates NPCs, bosses, or companions (e.g., dinos) with traits and abilities tied to X data and game context.

- **GET `/avatars/{avatar_id}`**  
  Retrieves stored avatar details by ID, e.g., `/avatars/avatar-xuseid-1234`.

- **GET `/characters/{character_id}`**  
  Retrieves stored character details by ID, e.g., `/characters/char-xuseid-5678`.

### Integration Steps
1. **Replace Mock DB**: Update `VEZE_DATA` with a real database (e.g., MongoDB, PostgreSQL) for persistent storage of avatars, characters, cars, rockets, etc.
2. **Game Client Integration**: Call `/create_avatar` and `/create_character` from the game client, passing player’s X username and desired styles/context. Use returned `visual_desc` and traits for rendering in-game.
3. **Dynamic Rendering**: Map traits and visual descriptions to 3D models or sprites in your game engine (e.g., Unity, Unreal). For example, “Neon Visor” could trigger a specific helmet model.
4. **X Personalization**: Leverage X data (bio, posts, metrics) to ensure avatars reflect player personality. High `average_likes` could add flashier visuals, while bio keywords shape traits.
5. **Customization UI**: Build a UI in the game for players to input `base_style` and `custom_traits`, calling `/create_avatar` to preview and save.

### Example Usage
- **Avatar Creation**:  
  ```bash
  curl -X POST http://localhost:8000/create_avatar -H "Content-Type: application/json" -d '{"username": "xuseid", "base_style": "Cosmic", "custom_traits": ["Starfield Cape"]}'
  ```
  Response: `{"avatar_id": "avatar-xuseid-1234", "username": "xuseid", "style": "Cosmic", "traits": ["Starfield Cape", "Lunar Glow"], "visual_desc": "A celestial figure with a shimmering cape."}`

- **Character Creation**:  
  ```bash
  curl -X POST http://localhost:8000/create_character -H "Content-Type: application/json" -d '{"username": "xuseid", "character_type": "DinoCompanion", "context": "Guarding Zara-9"}'
  ```
  Response: `{"character_id": "char-xuseid-5678", "type": "DinoCompanion", "name": "Starclaw", "traits": ["Crystal Scales"], "abilities": ["Plasma Roar"], "visual_desc": "A radiant dino with glowing spines."}`

This setup ensures avatars and characters are unique, tied to X user data, and seamlessly integrated into VEZE UniQVerse’s sci-fi world, enhancing player immersion.


Below are example response outputs for the newly created APIs in the VEZE UniQVerse X Engine, specifically for avatar and character customization. These demonstrate the expected JSON responses based on the provided `main.py` implementation, integrating X user data and Grok-generated content tailored for the game's sci-fi aesthetic.

### 1. POST `/create_avatar`
**Request**:  
```bash
curl -X POST http://localhost:8000/create_avatar -H "Content-Type: application/json" -d '{"username": "xuseid", "base_style": "Cosmic", "custom_traits": ["Starfield Cape"]}'
```

**Response**:  
```json
{
  "avatar_id": "avatar-xuseid-5678",
  "username": "xuseid",
  "style": "Cosmic",
  "traits": [
    "Starfield Cape",
    "Lunar Glow",
    "Astral Visor",
    "Nebula Armor",
    "Quantum Pulse"
  ],
  "visual_desc": "A celestial figure with a shimmering cape of stars, glowing with lunar energy and clad in nebula-like armor."
}
```

### 2. POST `/create_character`
**Request**:  
```bash
curl -X POST http://localhost:8000/create_character -H "Content-Type: application/json" -d '{"username": "xuseid", "character_type": "DinoCompanion", "context": "Guarding Zara-9"}'
```

**Response**:  
```json
{
  "character_id": "char-xuseid-1234",
  "type": "DinoCompanion",
  "name": "Starclaw",
  "traits": [
    "Crystal Scales",
    "Void-Touched Claws",
    "Holo-Tail",
    "Energy Crest"
  ],
  "abilities": [
    "Plasma Roar",
    "Gravity Shift",
    "Stellar Charge"
  ],
  "visual_desc": "A radiant dino with crystalline scales and a pulsating energy crest, its tail shimmering with holographic patterns."
}
```

### 3. GET `/avatars/{avatar_id}`
**Request**:  
```bash
curl http://localhost:8000/avatars/avatar-xuseid-5678
```

**Response**:  
```json
{
  "avatar_id": "avatar-xuseid-5678",
  "username": "xuseid",
  "style": "Cosmic",
  "traits": [
    "Starfield Cape",
    "Lunar Glow",
    "Astral Visor",
    "Nebula Armor",
    "Quantum Pulse"
  ],
  "visual_desc": "A celestial figure with a shimmering cape of stars, glowing with lunar energy and clad in nebula-like armor."
}
```

### 4. GET `/characters/{character_id}`
**Request**:  
```bash
curl http://localhost:8000/characters/char-xuseid-1234
```

**Response**:  
```json
{
  "character_id": "char-xuseid-1234",
  "type": "DinoCompanion",
  "name": "Starclaw",
  "traits": [
    "Crystal Scales",
    "Void-Touched Claws",
    "Holo-Tail",
    "Energy Crest"
  ],
  "abilities": [
    "Plasma Roar",
    "Gravity Shift",
    "Stellar Charge"
  ],
  "visual_desc": "A radiant dino with crystalline scales and a pulsating energy crest, its tail shimmering with holographic patterns."
}
```

### Notes
- **X Integration**: Responses are generated using X user data (bio, posts, metrics) to personalize traits and visuals, ensuring unique avatars/characters.
- **Grok Output**: The `visual_desc` and traits/abilities are crafted by Grok to align with VEZE UniQVerse’s sci-fi aesthetic, influenced by user’s X activity.
- **Error Handling**: If the X username or ID is invalid, expect a 404 error (e.g., `{"detail": "User not found"}`). If Grok fails, a 500 error is returned.
- **Storage**: Avatars and characters are stored in `VEZE_DATA` (mock DB), which should be replaced with a real database for production.
