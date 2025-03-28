# FR8 - Brainrot Video Automation 🎬⚡️

> **📝 Personal Note:** 
Hey FR8 — just to be fully transparent about how this came together. I got the email on Friday and immediately jumped into it over the weekend. I’m currently juggling two intense roles — one at a crypto company in Dubai and another with a U.S. quant fund — both very Python-heavy and demanding.

I knew I had to act fast if I wanted to do this right, so I started the project that weekend and have been working around my schedule ever since. I plan to wrap it up by this Friday. I just wanted to be clear that although I technically started before the official week, I’m not trying to cheat the system — I’ll also include a timestamped demo to back that up.

This project means a lot to me, and I’ve given it my full focus despite the chaos. No shortcuts — just commitment, late nights, and a genuine desire to build something meaningful with passion.
---

## 🧠 What is Brainrot Video Automation?

It's a free, open-source Python framework that transforms ordinary YouTube content into viral short-form videos for TikTok, Reels, and Shorts. The tool automatically identifies engaging moments, adds professional subtitles, and optimizes content for algorithm success—all without the expensive subscriptions to services like Opus Clip.

> **⏱️ Processing Time:** On average, generating one clip takes approximately 1.43 minutes. For optimal performance, avoid inputting lengthy videos as processing time scales with video duration.

I challenged myself to build what others pay hundreds for:  
**A complete, social video automation pipeline in just one week.**

This tool automatically:

- 📥 Downloads any YouTube video with a simple URL  
- ✂️ Intelligently identifies and extracts the most engaging moments  
- 🗣️ Generates accurate speech-to-text for professional subtitles  
- 📱 Reformats horizontal content for vertical 9:16 viewing  
- 🎮 Overlays trending background content (like Subway Surfers gameplay)  
- 🚀 Produces ready-to-upload content optimized for algorithm success

---

## 🛠️ What's Under the Hood?

This project leverages powerful open-source technologies:

- `yt-dlp`: Advanced YouTube downloader with format selection and metadata extraction
- `Auto-Editor`: Intelligent content analysis for identifying engaging moments through audio/visual cues
- `Whisper`: OpenAI's state-of-the-art speech recognition for accurate, timestamped transcription
- `ffmpeg`: Professional media processing engine for scaling, composition, and optimization
- `Streamlit`: Responsive web interface for easy interaction without technical knowledge

---
## 🧰 Project Components

- 🖥️ `workflow_app.py`: Simple web interface for tracking progress and batch processing
- ⚙️ `brainrot_workflow.py`: Main pipeline that runs all video processing steps in parallel
- 🎬 `movie.py`: Creates transcriptions and adds subtitles to videos
- ✂️ `highlights.py`: Finds the best parts of videos to keep viewers engaged
- 💬 `subtitle_styles.py`: Different text styles for subtitles with custom colors and sizes
- 📱 `video_formatter.py`: Converts videos to mobile format with correct dimensions
- 📥 `downloader.py`: Gets videos from YouTube with backup options if downloads fail

## 💡 Why I Built This

This project was born from my current work with a business partner on automating content for social media accounts. We've been developing systems for content recycling, Instagram scraping, and database integration for automated posting.

Rather than piecing together expensive third-party services, I saw an opportunity to build something that:

1. Solves a real problem I'm actively facing in my business
2. Demonstrates my engineering approach to FR8
3. Creates value as a truly open-source alternative to paid services

Video automation shouldn't require expensive subscriptions or deep technical knowledge.  
**With the right engineering, anyone can create high-quality, algorithm-friendly content — fast, free, and without limitations.**

## 📋 Installation & Usage Guide

### Prerequisites
- Python 3.8+ installed
- ffmpeg installed on your system (required for video processing)
- Auto-Editor (will be installed via pip)
- [Whisper](https://github.com/openai/whisper) or faster-whisper for transcription

### Step 1: Clone the repository
```bash
git clone https://github.com/elbarroca/FR8-Brainrot-Maker.git
cd FR8-Brainrot-Maker
```

### Step 2: Create a virtual environment
```bash
python -m venv venv
```

#### Activate the virtual environment
- On Windows:
  ```bash
  venv\Scripts\activate
  ```
- On macOS/Linux:
  ```bash
  source venv/bin/activate
  ```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

If requirements.txt is not available, install the following packages:
```bash
pip install streamlit yt-dlp auto-editor faster-whisper moviepy Pillow requests ffmpeg-python
```

### Step 4: Set up background videos
- Create an `assets` folder in the project directory
- Add MP4 videos to use as backgrounds (e.g., Subway Surfers gameplay)
```bash
mkdir -p assets
# Place your background videos in this folder
```

### Step 5: Run the Streamlit app
```bash
streamlit run workflow_app.py
```

This will launch the web interface on `http://localhost:8501`

### Step 6: Using the application
1. Paste a YouTube URL in the input field
2. Adjust settings as needed:
   - Select a background video
   - Configure subtitle style (size, color, etc.)
   - Set video quality
3. Click "Process YouTube Video"
4. Wait for the processing to complete
5. Preview, download, or share your generated clips

### Running from command line (Advanced)
If you prefer to use the application without the UI:
```bash
python brainrot_workflow.py --url "YOUTUBE_URL" --output-dir "output_directory" --background "path/to/background.mp4"
```