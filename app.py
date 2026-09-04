from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import time
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

# Create directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("videos", exist_ok=True)
os.makedirs("characters", exist_ok=True)

METADATA_FILE = "metadata.json"

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {"videos": [], "total_generations": 0, "characters": []}

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

@app.route('/health', methods=['GET'])
def health():
    metadata = load_metadata()
    return jsonify({
        "status": "running",
        "total_videos": len(metadata.get("videos", [])),
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

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    story_description = data.get('story_description', '')
    style = data.get('style', 'Pixar')
    
    metadata = load_metadata()
    characters = metadata.get("characters", [])
    char_names = [c.get('name', 'Character') for c in characters]
    char_list = ", ".join(char_names) if char_names else "The characters"
    
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
    
    timestamp = int(time.time())
    video_filename = f"video_{timestamp}.mp4"
    video_path = os.path.join("videos", video_filename)
    
    with open(video_path, 'wb') as f:
        f.write(b'')
    
    video_entry = {
        "filename": video_filename,
        "style": style,
        "created_at": datetime.now().isoformat(),
        "story": story_description,
        "scenes": scenes,
        "video_url": f"/videos/{video_filename}"
    }
    
    metadata = load_metadata()
    metadata["videos"].append(video_entry)
    metadata["total_generations"] += 1
    save_metadata(metadata)
    
    return jsonify({
        "status": "complete",
        "video_url": f"/videos/{video_filename}",
        "story": "\n".join(scenes),
        "scenes": scenes,
        "total_generations": metadata["total_generations"]
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

@app.route('/characters', methods=['GET'])
def get_characters():
    metadata = load_metadata()
    return jsonify({"characters": metadata.get("characters", [])})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
