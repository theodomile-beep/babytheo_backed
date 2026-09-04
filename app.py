from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import time
from datetime import datetime
import re
import requests
import base64

app = Flask(__name__)
CORS(app)

# ============================================
# LUMA AI CONFIGURATION
# ============================================
LUMA_API_KEY = "luma-api-SKkgr9gjQK2W_PYCv4J2anghDZ8rH_9t51R0OyEKXjQ"
LUMA_API_URL = "https://api.lumalabs.ai/dream-machine/v1/generations"

# ============================================
# CREATE DIRECTORIES
# ============================================
os.makedirs("uploads", exist_ok=True)
os.makedirs("videos", exist_ok=True)
os.makedirs("characters", exist_ok=True)

METADATA_FILE = "metadata.json"

# ============================================
# METADATA HELPERS
# ============================================

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {"videos": [], "total_generations": 0, "characters": []}

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

# ============================================
# LUMA AI VIDEO GENERATION
# ============================================

def generate_luma_video(prompt, style="Pixar"):
    """
    Generate a video using Luma AI API
    """
    headers = {
        "Authorization": f"Bearer {LUMA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Enhanced prompt for Pixar-style 3D animation
    style_prompts = {
        "Pixar": "Pixar-style 3D animation, heartwarming, colorful, smooth animation, child-friendly, soft shadows, global illumination, cinematic lighting, detailed environment, high quality CGI, toy-like texture, expressive characters, warm colors",
        "Cocomelon": "Cocomelon-style 2D/3D animation, bright colors, simple shapes, singing characters, educational, child-friendly, happy mood, colorful backgrounds",
        "Disney": "Disney-style 3D animation, magical, enchanting, detailed characters, beautiful landscapes, cinematic lighting, high quality CGI, emotional storytelling",
        "Dreamworks": "Dreamworks-style 3D animation, funny, energetic, expressive characters, dynamic action, colorful, high quality CGI, adventurous mood"
    }
    
    style_prompt = style_prompts.get(style, style_prompts["Pixar"])
    
    enhanced_prompt = f"""
    {prompt}
    Style: {style_prompt}
    Create a cinematic 3D animated scene with smooth character animation, 
    detailed environment, expressive characters, warm lighting, and professional quality.
    """
    
    payload = {
        "prompt": enhanced_prompt,
        "aspect_ratio": "16:9",
        "duration": 5,
        "loop": False,
        "motion": {
            "type": "auto"
        }
    }
    
    try:
        print(f"🎬 Starting Luma AI generation for: {prompt[:50]}...")
        
        # Start generation
        response = requests.post(LUMA_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        generation_id = data.get("id")
        if not generation_id:
            print("❌ No generation ID returned")
            return None
        
        print(f"✅ Generation started: {generation_id}")
        
        # Poll for completion
        status_url = f"{LUMA_API_URL}/{generation_id}"
        for attempt in range(120):  # Wait up to 2 minutes
            time.sleep(2)
            status_response = requests.get(status_url, headers=headers)
            status_data = status_response.json()
            
            state = status_data.get("state")
            print(f"⏳ Attempt {attempt+1}/120: State = {state}")
            
            if state == "completed":
                # Get video URL
                video_url = status_data.get("assets", {}).get("video")
                if video_url:
                    print(f"✅ Video generated successfully!")
                    return video_url
                else:
                    print("❌ No video URL in response")
                    return None
            elif state == "failed":
                error = status_data.get("failure_reason", "Unknown error")
                print(f"❌ Generation failed: {error}")
                return None
        
        print("⏰ Timeout waiting for video")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Luma AI API error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/health', methods=['GET'])
def health():
    metadata = load_metadata()
    return jsonify({
        "status": "running",
        "total_videos": len(metadata.get("videos", [])),
        "total_characters": len(metadata.get("characters", [])),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/upload-character', methods=['POST'])
def upload_character():
    if 'image' not in request.files:
        return jsonify({"error": "No image"}), 400
    
    file = request.files['image']
    name = request.form.get('name', f'Character {int(time.time())}')
    
    timestamp = int(time.time())
    filename = f"char_{timestamp}_{file.filename}"
    filepath = os.path.join("characters", filename)
    file.save(filepath)
    
    metadata = load_metadata()
    char_entry = {
        "id": timestamp,
        "name": name,
        "filename": filename,
        "created_at": datetime.now().isoformat()
    }
    metadata["characters"].append(char_entry)
    save_metadata(metadata)
    
    return jsonify({
        "status": "success",
        "filepath": filepath,
        "filename": filename,
        "name": name,
        "id": timestamp
    })

@app.route('/characters', methods=['GET'])
def get_characters():
    metadata = load_metadata()
    return jsonify({"characters": metadata.get("characters", [])})

@app.route('/delete-character/<int:char_id>', methods=['DELETE'])
def delete_character(char_id):
    metadata = load_metadata()
    characters = metadata.get("characters", [])
    
    for i, char in enumerate(characters):
        if char.get("id") == char_id:
            filepath = char.get("filepath")
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            characters.pop(i)
            break
    
    metadata["characters"] = characters
    save_metadata(metadata)
    return jsonify({"status": "deleted"})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    story_description = data.get('story_description', '')
    style = data.get('style', 'Pixar')
    
    if not story_description:
        return jsonify({"error": "No story provided"}), 400
    
    # Get characters
    metadata = load_metadata()
    characters = metadata.get("characters", [])
    char_names = [c.get('name', 'Character') for c in characters]
    char_list = ", ".join(char_names) if char_names else "The characters"
    
    # Generate scenes from story
    scenes = []
    sentences = re.split(r'[.!?]+', story_description)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        sentences = ["The characters go on an adventure together"]
    
    for i, sentence in enumerate(sentences[:6], 1):
        if not any(name in sentence for name in char_names):
            sentence = f"{char_list} {sentence.lower()}"
        scenes.append(f"{i}. {sentence}")
    
    while len(scenes) < 3:
        scenes.append(f"{len(scenes)+1}. The adventure continues")
    
    scenes = scenes[:6]
    
    # Generate video using Luma AI for the first scene (or combine)
    video_url_path = None
    luma_videos = []
    
    # Try to generate video with Luma AI
    if characters:
        # Create a prompt combining all scenes
        combined_prompt = f"{char_list}. "
        for scene in scenes:
            clean_scene = re.sub(r'^\d+\.\s*', '', scene)
            combined_prompt += f"{clean_scene}. "
        
        print(f"🎬 Generating video with prompt: {combined_prompt[:100]}...")
        luma_video_url = generate_luma_video(combined_prompt, style)
        
        if luma_video_url:
            # Download and save the video
            try:
                timestamp = int(time.time())
                video_filename = f"video_{timestamp}.mp4"
                video_path = os.path.join("videos", video_filename)
                
                response = requests.get(luma_video_url)
                with open(video_path, 'wb') as f:
                    f.write(response.content)
                
                video_url_path = f"/videos/{video_filename}"
                luma_videos.append({
                    "scene": "combined",
                    "url": luma_video_url,
                    "prompt": combined_prompt
                })
                print(f"✅ Video saved: {video_filename}")
            except Exception as e:
                print(f"❌ Error downloading video: {e}")
                video_url_path = None
    else:
        print("⚠️ No characters uploaded, skipping Luma AI generation")
    
    # If Luma failed, create placeholder
    if not video_url_path:
        timestamp = int(time.time())
        video_filename = f"video_{timestamp}.mp4"
        video_path = os.path.join("videos", video_filename)
        
        with open(video_path, 'wb') as f:
            f.write(b'')
        
        video_url_path = f"/videos/{video_filename}"
    
    # Save to metadata
    video_entry = {
        "filename": video_filename,
        "style": style,
        "created_at": datetime.now().isoformat(),
        "story": story_description,
        "scenes": scenes,
        "video_url": video_url_path,
        "luma_generated": bool(luma_videos),
        "luma_videos": luma_videos,
        "characters_used": char_names
    }
    
    metadata = load_metadata()
    metadata["videos"].append(video_entry)
    metadata["total_generations"] += 1
    save_metadata(metadata)
    
    # Prepare response
    story_text = "\n".join(scenes)
    
    return jsonify({
        "status": "complete",
        "video_url": video_url_path,
        "story": story_text,
        "scenes": scenes,
        "total_generations": metadata["total_generations"],
        "luma_generated": bool(luma_videos),
        "luma_videos": luma_videos,
        "characters_used": char_names
    })

@app.route('/videos/<filename>', methods=['GET'])
def get_video(filename):
    return send_from_directory("videos", filename)

@app.route('/history', methods=['GET'])
def get_history():
    metadata = load_metadata()
    return jsonify({
        "total_generations": metadata.get("total_generations", 0),
        "videos": metadata.get("videos", [])
    })

@app.route('/story', methods=['GET'])
def get_story():
    metadata = load_metadata()
    return jsonify({
        "last_story": metadata.get("last_story", {}),
        "last_video": metadata.get("last_video", {})
    })

@app.route('/clear-history', methods=['POST'])
def clear_history():
    metadata = load_metadata()
    metadata["videos"] = []
    metadata["total_generations"] = 0
    save_metadata(metadata)
    return jsonify({"status": "cleared"})

@app.route('/sample-video', methods=['GET'])
def sample_video():
    """Return a sample video URL for testing"""
    return jsonify({
        "video_url": "https://sample-videos.com/video321/mp4/240/big_buck_bunny_240p_1mb.mp4"
    })

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
