# Brainrot Video Automation

A tool to transform videos into short-form vertical clips with engaging overlay, suitable for TikTok, Reels, and Shorts.

## Overview

This project provides two main interfaces:

1. A Streamlit web application (`app.py`)
2. A command-line tool (`main.py`)

Both interfaces leverage the same core functionality to:

- Download YouTube videos
- Extract highlight clips automatically
- Add subtitles with animation effects
- Stack videos with a background (e.g., Subway Surfers gameplay)
- Format for vertical 9:16 social media

This system automates the creation of "brainrot" style videos:
1. Downloads videos from YouTube links
2. Extracts highlight clips using auto-editor
3. Adds subtitles using Whisper transcription
4. Formats videos for mobile viewing (9:16 aspect ratio)
5. Stacks them with background videos (e.g., Subway Surfers)
6. Produces social media ready content

## Project Structure

- `app.py`: Streamlit web interface with tabs for uploading videos or downloading from YouTube
- `main.py`: Command-line tool for batch processing videos
- `movie.py`: Core module for video transcription and subtitle generation
- Additional modules:
  - `highlights.py`: For extracting highlight clips
  - `auto_subtitle.py`: For generating subtitles
  - `video_formatter.py`: For video processing operations
  - `downloader.py`: For downloading YouTube videos

## Features

- **Smart Highlight Extraction**: Automatically extracts 20-40 second highlight clips using audio and motion detection
- **Automatic Subtitles**: Uses Whisper to generate accurate subtitles for each highlight clip
- **Appealing Dynamic Subtitles**: Option to use JSON2Video API for professionally animated subtitles
- **Multi-Clip Processing**: Handles batch processing of multiple videos
- **Mobile-Optimized Format**: Formats videos for mobile viewing in 9:16 ratio without cropping content
- **Gradient Transitions**: Adds smooth transitions between highlight and background videos
- **Background Video**: Adds looping Subway Surfers (or other background) gameplay to the bottom half

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. If you encounter NumPy compatibility issues, downgrade NumPy:
   ```
   pip install numpy==1.26.4 --force-reinstall
   ```

3. Ensure you have ffmpeg installed:
   - macOS: `brew install ffmpeg`
   - Linux: `apt install ffmpeg`
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

4. Install Auto-Editor:
   ```
   pip install auto-editor
   ```

5. Install Whisper for subtitles:
   ```
   pip install openai-whisper
   ```

6. Create an `assets` folder and add a background video (optional):
   ```
   mkdir -p assets
   ```
   
   You can add your own `assets/dummy_background.mp4` file to use as default background.

## Usage

### Web Interface (Streamlit)

```bash
streamlit run app.py
```

### Command-Line

```bash
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir output
```

For batch processing:
```bash
python main.py --urls-file urls.txt --output-dir output
```

## Advanced Features

- Customizable highlight extraction (length, threshold)
- Various subtitle styles and animations
- Support for custom background videos
- Batch processing of multiple videos

## Processing Steps

For each highlight clip:

1. Download YouTube video using yt-dlp
2. Extract multiple highlight clips using improved detection:
   - Combines scene detection with audio analysis
   - Detects speech segments and motion changes
   - Ensures optimal clip duration for social media engagement
   - Ranks clips by quality score based on duration, position, and audio levels
3. Generate accurate subtitles using Whisper AI or WhisperX for better timestamps
4. Process subtitles in one of two ways:
   - Standard: Burn subtitles directly into video with enhanced formatting
   - JSON2Video (if enabled): Create dynamic animated subtitles with fade effects and modern styling
5. Format for mobile viewing in 9:16 aspect ratio (1080x1920) preserving all content (no cropping)
6. Loop background video to match highlight duration
7. Stack videos with smooth gradient transition between sections
8. Optimize for social media platforms with 2-pass encoding

## Auto-Editor Configuration

The system uses Auto-Editor with these optimized settings:
- `--silent-threshold 0.03`: Better sensitivity for speech detection
- `--frame-margin 6`: Keeps small buffer around speaking parts
- `--min-clip-length 20`: Ensures highlights are at least 20 seconds
- `--max-clip-length 40`: Caps highlights at 40 seconds for social media
- `--video-speed 1`: Maintains natural pace without speedups

## Troubleshooting

- **NumPy Version Issues**: If you see NumPy compatibility errors, run `pip install numpy==1.26.4 --force-reinstall`
- **Missing FFmpeg**: Ensure ffmpeg is installed and available in your PATH
- **Auto-Editor Issues**: If auto-editor fails, try reinstalling with `pip install --upgrade auto-editor`
- **Whisper Failures**: If Whisper fails, the system will fall back to basic subtitle generation
- **No Highlights Detected**: The system will fall back to scene detection if Auto-Editor fails to find highlights

## Examples

Create brain rot clips with default settings:
```
python main.py --url https://www.youtube.com/watch?v=OGtetvg2pS8
```

Process a list of videos:
```
python main.py --urls-file videos.txt
```

Use a custom background video and custom output directory:
```
python main.py --url https://www.youtube.com/watch?v=OGtetvg2pS8 --subway-video my_background.mp4 --output-dir my_videos
```

Process with JSON2Video subtitles for more appealing animations:
```
python main.py --url https://www.youtube.com/watch?v=OGtetvg2pS8 --use-json2video --json2video-api-key YOUR_API_KEY
```

Process with lower concurrency for resource-constrained systems:
```
python main.py --urls-file videos.txt --max-concurrent 1
```

Test mobile formatting on a single video:
```
python test_mobile_format.py path/to/video.mp4 --use-json2video
```

## JSON2Video Integration

The system can use the JSON2Video API for creating professional-looking animated subtitles:

- **Dynamic Text Elements**: Subtitles appear with smooth fade-in/fade-out animations
- **Enhanced Readability**: Text size dynamically adjusts based on content length
- **Modern Styling**: Rounded background elements with proper padding and contrast
- **Precise Timing**: Subtitles are accurately synchronized with speech

To use this feature:
1. Ensure you have an API key from [JSON2Video](https://json2video.com/)
2. Pass the key via `--json2video-api-key` or set the JSON2VIDEO_API_KEY environment variable
3. Enable JSON2Video with the `--use-json2video` flag

Example:
```
python main.py --url https://www.youtube.com/watch?v=OGtetvg2pS8 --use-json2video --json2video-api-key YOUR_API_KEY
```

If JSON2Video processing fails for any reason, the system will automatically fall back to standard subtitle burning.

## Using the Pipeline Script

The `brainrot_pipeline.py` script provides a complete end-to-end workflow for creating brainrot videos:

```bash
# Basic usage
python brainrot_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Specify output directory
python brainrot_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir "my_videos"

# Use a specific Subway Surfers video
python brainrot_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --subway-video "/path/to/subway.mp4"
```

### Workflow Details

The script follows this process:
1. **Download**: Uses the VideoDownloader to fetch the YouTube video
2. **Extract Highlights**: Uses auto-editor to identify interesting segments (10-40 seconds long)
3. **Format for Mobile**: Resizes video to 9:16 aspect ratio for mobile viewing
4. **Transcribe**: Uses Whisper to generate word-level transcription
5. **Add Subtitles**: Adds highlighted subtitles to the video clips
6. **Add Background**: Stacks the video with a Subway Surfers background
7. **Optimize**: Compresses the final video for social media platforms

### Customization

You can adjust the highlight extraction parameters by modifying these values in the script:
- `min_clip_duration`: Minimum length of extracted clips (default: 10 seconds)
- `max_clip_duration`: Maximum length of extracted clips (default: 40 seconds)
- `max_clips_per_video`: Maximum number of clips to extract (default: 5)

## License

MIT 