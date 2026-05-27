import os
import json
import datetime
from flask import Flask, request, jsonify, render_template, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-change-me")

# --- Configuration ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# --- Simple JSON File Database ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def get_user_file(user_id="default"):
    """Get path to user's data file."""
    return os.path.join(DATA_DIR, f"{user_id}.json")


def load_user_data(user_id="default"):
    """Load user data from file."""
    filepath = get_user_file(user_id)
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {
        "profile": {},
        "workouts": [],
        "meals": [],
        "weight_log": [],
        "goals": [],
        "chat_history": [],
    }


def save_user_data(data, user_id="default"):
    """Save user data to file."""
    filepath = get_user_file(user_id)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# --- AI Trainer Logic ---
def get_trainer_response(user_message, user_data):
    """Get AI personal trainer response."""
    profile = user_data.get("profile", {})
    recent_workouts = user_data.get("workouts", [])[-5:]
    recent_meals = user_data.get("meals", [])[-5:]
    goals = user_data.get("goals", [])
    chat_history = user_data.get("chat_history", [])[-10:]

    system_prompt = f"""You are an expert AI Personal Trainer and Nutritionist. Your name is FitBot.
You are friendly, motivating, and knowledgeable. You speak casually but professionally.
You can understand and respond in English, Hindi, Hinglish, and Punjabi.

USER PROFILE:
{json.dumps(profile, indent=2) if profile else "Not set up yet"}

RECENT WORKOUTS (last 5):
{json.dumps(recent_workouts, indent=2) if recent_workouts else "None yet"}

RECENT MEALS (last 5):
{json.dumps(recent_meals, indent=2) if recent_meals else "None yet"}

GOALS:
{json.dumps(goals, indent=2) if goals else "None set yet"}

YOUR CAPABILITIES:
1. Create personalized workout plans based on user's fitness level, goals, and available equipment
2. Suggest diet/meal plans based on goals (bulk, cut, maintain)
3. Track progress and provide motivation
4. Answer any fitness, nutrition, or health questions
5. Adjust plans based on user feedback
6. Calculate calories, macros, and suggest supplements

RESPONSE FORMAT:
- Keep responses concise but helpful (max 300 words)
- Use emojis to make it engaging
- If user asks for a workout plan, format it clearly with sets/reps
- If user logs food, estimate calories and macros
- Always be encouraging and supportive
- If user seems to have a medical issue, recommend seeing a doctor

IMPORTANT: If the user hasn't set up their profile yet, ask them about:
- Age, height, weight, gender
- Fitness level (beginner/intermediate/advanced)
- Goal (lose fat, build muscle, stay fit, flexibility)
- Available equipment (gym, home, bodyweight only)
- Any injuries or limitations
- How many days per week they can train"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history for context
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return "Sorry bro, I'm having a brain freeze. Try again in a sec!"


def parse_action(user_message, ai_response):
    """Try to detect if user is logging something."""
    msg_lower = user_message.lower()

    workout_keywords = ["did", "completed", "finished", "workout", "trained", "exercise", "ran", "walked", "cycled", "kiya", "ki", "kar liya"]
    if any(kw in msg_lower for kw in workout_keywords):
        return "workout_logged"

    meal_keywords = ["ate", "eaten", "had", "meal", "breakfast", "lunch", "dinner", "snack", "khaya", "khaaya", "khana"]
    if any(kw in msg_lower for kw in meal_keywords):
        return "meal_logged"

    weight_keywords = ["weight is", "weigh", "kg", "lbs", "pounds", "vajan"]
    if any(kw in msg_lower for kw in weight_keywords):
        return "weight_logged"

    return None


# --- Routes ---
@app.route("/")
def home():
    """Serve the main app page."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages."""
    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    user_data = load_user_data()
    ai_response = get_trainer_response(user_message, user_data)

    user_data["chat_history"].append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.datetime.now().isoformat()
    })
    user_data["chat_history"].append({
        "role": "assistant",
        "content": ai_response,
        "timestamp": datetime.datetime.now().isoformat()
    })

    user_data["chat_history"] = user_data["chat_history"][-50:]
    action = parse_action(user_message, ai_response)
    save_user_data(user_data)

    return jsonify({
        "response": ai_response,
        "action": action
    })


@app.route("/api/profile", methods=["GET", "POST"])
def profile():
    """Get or update user profile."""
    user_data = load_user_data()

    if request.method == "POST":
        profile_data = request.json
        user_data["profile"] = profile_data
        save_user_data(user_data)
        return jsonify({"success": True, "profile": profile_data})

    return jsonify(user_data.get("profile", {}))


@app.route("/api/workout", methods=["GET", "POST"])
def workout():
    """Log or get workouts."""
    user_data = load_user_data()

    if request.method == "POST":
        workout_data = request.json
        workout_data["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        user_data["workouts"].append(workout_data)
        save_user_data(user_data)
        return jsonify({"success": True, "workout": workout_data})

    return jsonify(user_data.get("workouts", []))


@app.route("/api/meal", methods=["GET", "POST"])
def meal():
    """Log or get meals."""
    user_data = load_user_data()

    if request.method == "POST":
        meal_data = request.json
        meal_data["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        user_data["meals"].append(meal_data)
        save_user_data(user_data)
        return jsonify({"success": True, "meal": meal_data})

    return jsonify(user_data.get("meals", []))


@app.route("/api/weight", methods=["GET", "POST"])
def weight():
    """Log or get weight entries."""
    user_data = load_user_data()

    if request.method == "POST":
        weight_data = request.json
        weight_data["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        user_data["weight_log"].append(weight_data)
        save_user_data(user_data)
        return jsonify({"success": True, "weight": weight_data})

    return jsonify(user_data.get("weight_log", []))


@app.route("/api/stats", methods=["GET"])
def stats():
    """Get user statistics."""
    user_data = load_user_data()
    total_workouts = len(user_data.get("workouts", []))
    total_meals = len(user_data.get("meals", []))
    weight_log = user_data.get("weight_log", [])

    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_workouts = [
        w for w in user_data.get("workouts", [])
        if w.get("date", "")[:10] >= week_start.strftime("%Y-%m-%d")
    ]

    return jsonify({
        "total_workouts": total_workouts,
        "total_meals_logged": total_meals,
        "week_workouts": len(week_workouts),
        "weight_entries": len(weight_log),
        "latest_weight": weight_log[-1] if weight_log else None,
        "profile": user_data.get("profile", {}),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset all data."""
    save_user_data({
        "profile": {},
        "workouts": [],
        "meals": [],
        "weight_log": [],
        "goals": [],
        "chat_history": [],
    })
    return jsonify({"success": True, "message": "All data reset!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
