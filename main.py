#!/usr/bin/env python3
import argparse
import asyncio
import os
import time
import shutil
from pathlib import Path

# Import our modules
from highlights import HighlightExtractor
from video_formatter import VideoFormatter
from downloader import VideoDownloader
import movie

# Create replacement functions for auto_subtitle to maintain API compatibility
def generate_subtitle(video_path, output_dir, model="small", task="transcribe", subtitle_style="brainrot"):
    """Generate subtitles using movie.py functionality"""
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Extract audio from video
        audio_path = movie.create_audio(str(video_path))
        
        # Load whisper model
        whisper_model = movie.load_whisper_model(model)
        
        # Transcribe the audio
        wordlevel_info = movie.transcribe_audio(whisper_model, audio_path)
        
        # Generate SRT file path
        video_path = Path(video_path)
        srt_path = output_dir / f"{video_path.stem}.srt"
        
        # Setup standard parameters
        v_type = "reels"
        subs_position = "bottom"
        highlight_color = "#ffffff"
        fontsize = 5
        opacity = 0.7
        MaxChars = 40
        color = "#cccccc"
        
        # Generate SRT file
        linelevel_subtitles = movie.split_text_into_lines(wordlevel_info, v_type, MaxChars)
        
        # Write SRT file
        with open(srt_path, 'w') as f:
            for i, line in enumerate(linelevel_subtitles):
                start_time = format_time(line['start'])
                end_time = format_time(line['end'])
                f.write(f"{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{line['word']}\n\n")
        
        print(f"✅ Generated subtitle file: {srt_path}")
        return str(srt_path)
        
    except Exception as e:
        print(f"❌ Error generating subtitle with movie.py: {e}")
        return None

def generate_whisper_subtitle(video_path, output_dir, model="small", subtitle_style="brainrot"):
    """Generate subtitles using whisper directly via movie.py"""
    # This is just an alias to maintain API compatibility
    return generate_subtitle(video_path, output_dir, model, "transcribe", subtitle_style)

def format_time(seconds):
    """Format time in SRT format (HH:MM:SS,mmm)"""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

async def process_video(url, output_dir, subway_video_path, cpu_bound_semaphore, config=None):
    """Process a single video through the full pipeline with enhanced parallelism"""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Extract video ID from URL for consistent naming
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    elif "youtube.com" in url and "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    else:
        # Use timestamp as fallback
        video_id = f"video_{int(time.time())}"
    
    print(f"🔄 Processing video: {url} (ID: {video_id})")
    
    # Step 1: Download video with retry mechanism
    max_download_attempts = 3
    input_video = None
    
    for attempt in range(max_download_attempts):
        try:
            start_time = time.time()
            downloader = VideoDownloader(str(output_dir))
            input_video = await asyncio.to_thread(downloader.download_youtube, url)
            if input_video:
                print(f"✅ Download complete ({time.time() - start_time:.2f}s)")
                break
            print(f"⚠️ Download attempt {attempt+1} failed, retrying...")
        except Exception as e:
            print(f"❌ Error during download attempt {attempt+1}: {e}")
            if attempt < max_download_attempts - 1:
                print(f"Retrying download in 3 seconds...")
                await asyncio.sleep(3)
    
    if not input_video:
        print(f"❌ All download attempts failed for {url}")
        return None
    
    # Step 2: Extract highlights with improved parallelism
    try:
        start_time = time.time()
        # Use semaphore only for highlight extraction which is CPU-intensive
        async with cpu_bound_semaphore:
            highlight_extractor = HighlightExtractor(output_dir)
            
            # Configure highlight extraction using provided config or defaults
            if config:
                highlight_extractor.min_clip_duration = config.get('min_clip_duration', 6)
                highlight_extractor.max_clip_duration = config.get('max_clip_duration', 30)
                highlight_extractor.scene_threshold = config.get('scene_threshold', 0.15)
                highlight_extractor.max_clips_per_video = config.get('max_clips', 10)
            
            # Extract highlights with configured settings
            print(f"Extracting highlights with scene_threshold={highlight_extractor.scene_threshold}, min_duration={highlight_extractor.min_clip_duration}s")
            highlight_clips = await highlight_extractor.extract_highlights_async(input_video)
            
            clip_count = len(highlight_clips) if highlight_clips else 0
            print(f"✅ Highlights processing complete: extracted {clip_count} clips ({time.time() - start_time:.2f}s)")
    except Exception as e:
        print(f"❌ Error during highlight extraction: {e}")
        # Use original video as fallback
        fallback_filename = f"highlight_{video_id}_1.mp4"
        fallback_path = output_dir / fallback_filename
        shutil.copy2(input_video, fallback_path)
        highlight_clips = [fallback_path]
        print(f"⚠️ Using original video as fallback due to highlight extraction error")
    
    # Initialize tools for the rest of the pipeline
    formatter = VideoFormatter(output_dir)
    
    # Set JSON2Video usage if specified in config
    use_json2video = config.get('use_json2video', False)
    if use_json2video:
        # Check if JSON2VIDEO_API_KEY is already in environment
        # Only set it from config if not already present
        json2video_api_key = os.environ.get('JSON2VIDEO_API_KEY')
        if not json2video_api_key:
            json2video_api_key = config.get('json2video_api_key')
            if json2video_api_key:
                os.environ['JSON2VIDEO_API_KEY'] = json2video_api_key
        print("🎬 Using JSON2Video for enhanced subtitles")
    
    # Process clips in parallel with concurrency control
    async def process_single_clip(clip_index, highlight):
        clip_id = f"{video_id}_{clip_index+1}"
        
        # FIRST: Format video for mobile viewing (CPU-bound operation)
        async with cpu_bound_semaphore:
            mobile_clip_filename = f"mobile_clip_{clip_id}.mp4"
            try:
                start_time = time.time()
                mobile_clip = await asyncio.to_thread(formatter.format_for_mobile, highlight, mobile_clip_filename)
                if not mobile_clip:
                    print(f"❌ Failed to format video for mobile for clip {clip_index+1}.")
                    return None
                print(f"✅ Video formatted for mobile viewing for clip {clip_index+1} ({time.time() - start_time:.2f}s)")
            except Exception as e:
                print(f"❌ Error during mobile formatting for clip {clip_index+1}: {e}")
                return None
        
        # SECOND: Generate subtitles (CPU-bound operation)
        async with cpu_bound_semaphore:
            subtitle_filename = f"subtitles_{clip_id}.srt"
            try:
                start_time = time.time()
                # Try to generate subtitles with auto_subtitle first
                subtitle_file = await asyncio.to_thread(generate_subtitle, mobile_clip, output_dir, "small", "transcribe")
                
                # If that fails, try with whisper directly
                if not subtitle_file:
                    print(f"⚠️ Trying with whisper directly for clip {clip_index+1}...")
                    subtitle_file = await asyncio.to_thread(generate_whisper_subtitle, mobile_clip, output_dir, "small")
                
                if subtitle_file:
                    print(f"✅ Subtitles generated for clip {clip_index+1} ({time.time() - start_time:.2f}s)")
                    # Rename the subtitle file to match our expected naming convention
                    original_subtitle = Path(subtitle_file)
                    new_subtitle_path = output_dir / subtitle_filename
                    if original_subtitle.exists() and original_subtitle != new_subtitle_path:
                        shutil.copy2(original_subtitle, new_subtitle_path)
                        subtitle_file = str(new_subtitle_path)
                else:
                    print(f"❌ Failed to generate subtitles for clip {clip_index+1}. Creating empty subtitle file.")
                    subtitle_file = output_dir / subtitle_filename
                    with open(subtitle_file, 'w') as f:
                        f.write("1\n00:00:00,000 --> 00:00:05,000\n\n")
                    subtitle_file = str(subtitle_file)
            except Exception as e:
                print(f"❌ Error during subtitle generation for clip {clip_index+1}: {e}")
                subtitle_file = output_dir / subtitle_filename
                with open(subtitle_file, 'w') as f:
                    f.write("1\n00:00:00,000 --> 00:00:05,000\n\n")
                subtitle_file = str(subtitle_file)
        
        # THIRD: Burn subtitles (CPU-bound operation)
        async with cpu_bound_semaphore:
            subbed_video_filename = f"subbed_{clip_id}.mp4"
            try:
                start_time = time.time()
                # Force JSON2Video if enabled through config
                if use_json2video:
                    # Set environment variable to ensure JSON2Video is used
                    os.environ['USE_JSON2VIDEO'] = 'true'
                
                video_with_subtitles = await asyncio.to_thread(formatter.burn_subtitles, mobile_clip, subtitle_file, subbed_video_filename)
                
                if use_json2video:
                    # Clean up environment variable
                    os.environ.pop('USE_JSON2VIDEO', None)
                
                if video_with_subtitles:
                    print(f"✅ Subtitles processing complete for clip {clip_index+1} ({time.time() - start_time:.2f}s)")
                else:
                    print(f"❌ Failed to process subtitles for clip {clip_index+1}. Using mobile video without subtitles.")
                    video_with_subtitles = mobile_clip
            except Exception as e:
                print(f"❌ Error during subtitle processing for clip {clip_index+1}: {e}")
                video_with_subtitles = mobile_clip
        
        # FOURTH: Prepare background and stack videos
        duration = formatter.get_video_duration(video_with_subtitles)
        
        # Create tasks for background preparation and stacking
        bottom_clip_task = asyncio.create_task(prepare_background(clip_id, duration, video_with_subtitles))
        
        try:
            final_video = await bottom_clip_task
            if final_video:
                print(f"🎬 Completed processing for clip {clip_index+1}: {final_video}")
                return final_video
        except Exception as e:
            print(f"❌ Error in final video processing for clip {clip_index+1}: {e}")
            return None
    
    # Helper function for background and stacking operations
    async def prepare_background(clip_id, duration, mobile_clip):
        # Prepare background video
        async with cpu_bound_semaphore:
            bottom_clip_filename = f"bottom_clip_{clip_id}.mp4"
            try:
                start_time = time.time()
                bottom_clip = await asyncio.to_thread(formatter.loop_subway_surfers, subway_video_path, duration, bottom_clip_filename)
                if not bottom_clip:
                    print(f"❌ ERROR: Could not create background video. Please ensure Subway Surfer Gameplay.mp4 exists")
                    return None
                print(f"✅ Background video prepared ({time.time() - start_time:.2f}s)")
            except Exception as e:
                print(f"❌ Error preparing background: {e}")
                return None
        
        # Stack videos
        async with cpu_bound_semaphore:
            stacked_video_filename = f"stacked_{clip_id}.mp4"
            try:
                start_time = time.time()
                stacked_video = await asyncio.to_thread(formatter.stack_videos, mobile_clip, bottom_clip, stacked_video_filename)
                if not stacked_video:
                    return None
                print(f"✅ Videos stacked ({time.time() - start_time:.2f}s)")
            except Exception as e:
                print(f"❌ Error stacking videos: {e}")
                return None
        
        # Optimize video (less CPU-intensive, can run without semaphore)
        final_video_filename = f"final_{clip_id}.mp4"
        try:
            start_time = time.time()
            final_video = await asyncio.to_thread(formatter.optimize_video, stacked_video, final_video_filename)
            if not final_video:
                print(f"⚠️ Video optimization failed. Using stacked version.")
                final_video = stacked_video
            else:
                print(f"✅ Video optimized ({time.time() - start_time:.2f}s)")
            return final_video
        except Exception as e:
            print(f"⚠️ Error optimizing video: {e}")
            return stacked_video
    
    # Process all clips in parallel with controlled concurrency
    start_time = time.time()
    clip_tasks = [process_single_clip(i, clip) for i, clip in enumerate(highlight_clips)]
    results = await asyncio.gather(*clip_tasks, return_exceptions=True)
    
    # Filter out exceptions and failed clips
    final_videos = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ Error processing clip {i+1}: {result}")
        elif result:
            final_videos.append(result)
    
    total_time = time.time() - start_time
    print(f"🎉 Processing complete for {url}. Created {len(final_videos)} final videos (Total: {total_time:.2f}s)")
    return final_videos

async def main_async():
    parser = argparse.ArgumentParser(description="Brainrot Video Automation Tool")
    parser.add_argument("--url", help="YouTube URL to download")
    parser.add_argument("--urls-file", help="File containing list of YouTube URLs (one per line)")
    parser.add_argument("--output-dir", default="output", help="Directory to save output files")
    parser.add_argument("--subway-video", help="Path to Subway Surfers video file (optional, will create dummy video if not provided)")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Maximum number of videos to process concurrently")
    parser.add_argument("--min-clip-duration", type=int, default=10, help="Minimum duration of highlight clips in seconds")
    parser.add_argument("--max-clip-duration", type=int, default=40, help="Maximum duration of highlight clips in seconds")
    parser.add_argument("--scene-threshold", type=float, default=0.20, help="Scene detection threshold (lower = more clips)")
    parser.add_argument("--max-clips", type=int, default=10, help="Maximum number of highlight clips to extract per video")
    parser.add_argument("--min-clips", type=int, default=3, help="Minimum number of clips to aim for (will use more permissive settings if needed)")
    parser.add_argument("--use-json2video", action="store_true", help="Use JSON2Video API for more appealing subtitles")
    parser.add_argument("--json2video-api-key", help="API key for JSON2Video (optional)")
    
    args = parser.parse_args()
    
    # Validate input
    if not args.url and not args.urls_file:
        parser.error("Please provide either a YouTube URL with --url or a file with URLs using --urls_file")
    
    # Collect all URLs to process
    urls = []
    if args.url:
        urls.append(args.url)
    if args.urls_file:
        with open(args.urls_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
                    
    if not urls:
        print("No valid URLs to process")
        return

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Ensure we have a background video
    subway_video_path = args.subway_video
    if not subway_video_path or not os.path.exists(subway_video_path):
        # Try to find Subway Surfer Gameplay.mp4 in various locations
        possible_paths = [
            Path("assets/Subway Surfer Gameplay.mp4"),
            Path("./Subway Surfer Gameplay.mp4"),
            Path("./assets/Subway Surfer Gameplay.mp4"),
            Path("../assets/Subway Surfer Gameplay.mp4"),
            Path("/Users/barroca888/FR8/Brainrot Automacion/assets/Subway Surfer Gameplay.mp4")
        ]
        
        for path in possible_paths:
            if path.exists():
                subway_video_path = str(path)
                print(f"✅ Found Subway Surfer Gameplay at: {subway_video_path}")
                break
        
        if not subway_video_path or not os.path.exists(subway_video_path):
            print("❌ ERROR: Subway Surfer Gameplay.mp4 not found!")
            print("Please place the video in the assets folder or specify it with --subway-video")
            return
    
    # Create a semaphore to limit CPU-bound operations
    cpu_bound_semaphore = asyncio.Semaphore(args.max_concurrent)
    
    # Process all videos concurrently
    start_time = time.time()
    print(f"🚀 Starting batch processing of {len(urls)} videos...")
    
    # Create tasks for all videos
    tasks = [process_video(url, output_dir, subway_video_path, cpu_bound_semaphore, 
             {'min_clip_duration': args.min_clip_duration, 
              'max_clip_duration': args.max_clip_duration, 
              'scene_threshold': args.scene_threshold, 
              'max_clips': args.max_clips,
              'min_clips': args.min_clips,
              'use_json2video': args.use_json2video,
              'json2video_api_key': args.json2video_api_key}) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and count successful results
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ Error processing URL {urls[i]}: {result}")
        elif result:
            valid_results.extend(result if isinstance(result, list) else [result])
    
    # Print final report
    total_time = time.time() - start_time
    print(f"\n====== FINAL REPORT ======")
    print(f"📊 Total videos processed: {len(urls)}")
    print(f"✅ Successfully created: {len(valid_results)} clips")
    print(f"⏱️ Total processing time: {total_time:.2f} seconds")
    print(f"📂 Output directory: {output_dir.absolute()}")
    print(f"========================\n")
    
    for clip in valid_results:
        print(f"📹 {clip}")

def main():
    """Entry point for the script"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main() 