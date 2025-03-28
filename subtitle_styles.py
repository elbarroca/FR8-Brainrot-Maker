#!/usr/bin/env python3
import os
import sys
import asyncio
from pathlib import Path
import time
import argparse
import tempfile
import subprocess

# Import modules from the movie.py script
from movie import load_whisper_model, create_audio, transcribe_audio, add_subtitle

# Define style presets
SUBTITLE_STYLES = {
    "default": {
        "font_size": 36,
        "text_color": "FFFFFF",
        "use_outline": True,
        "outline_color": "000000",
    },
    "large_white": {
        "font_size": 36,
        "text_color": "FFFFFF",  # White
        "use_outline": True,
        "outline_color": "000000",  # Black
    },
    "red_no_outline": {
        "font_size": 30,
        "text_color": "FF0000",  # Red
        "use_outline": False,
        "outline_color": None,
    },
    "tiktok_style": {
        "font_size": 42,
        "text_color": "FFFFFF",  # White
        "use_outline": True,
        "outline_color": "000000",  # Black
    },
    "blue_white_outline": {
        "font_size": 28,
        "text_color": "0000FF",  # Blue
        "use_outline": True,
        "outline_color": "FFFFFF",  # White outline
    },
    "green_black_outline": {
        "font_size": 32,
        "text_color": "00FF00",  # Green
        "use_outline": True,
        "outline_color": "000000",  # Black
    },
    "pink_bold": {
        "font_size": 38,
        "text_color": "FF00FF",  # Pink
        "use_outline": True,
        "outline_color": "000000",  # Black
    },
    "focus_style": {
        "font_size": 42,
        "text_color": "FFFFFF",  # White text
        "use_outline": True,
        "outline_color": "000000",  # Black outline with extra thickness
    }
}

async def apply_subtitle_style(
    input_video,
    output_dir,
    style_name,
    style_config,
    model=None,
    audio_path=None,
    word_level_info=None
):
    """Apply a specific subtitle style to a video"""
    style_output_dir = os.path.join(output_dir, style_name)
    os.makedirs(style_output_dir, exist_ok=True)
    
    print(f"\n--- Testing style: {style_name} ---")
    print(f"Settings: {style_config}")
    
    # Extract audio only once if not provided
    if not audio_path:
        print("Extracting audio...")
        audio_path = create_audio(input_video)
        if not audio_path:
            print("Failed to extract audio")
            return None
    
    # Load model only once if not provided
    if model is None:
        print("Loading Whisper model...")
        model = load_whisper_model("small")
    
    # Transcribe only once if not provided
    if word_level_info is None:
        print("Transcribing audio...")
        word_level_info = transcribe_audio(model, audio_path)
    
    # Get configuration values with defaults
    font_size = int(style_config.get("font_size", 7))
    text_color = style_config.get("text_color", "FFFF00")
    use_outline = style_config.get("use_outline", True)
    outline_color = style_config.get("outline_color", "000000") if use_outline else None
    
    # Monkey patch the create_caption function to handle our outline settings
    from movie import create_caption as original_create_caption
    import functools
    
    def create_caption_wrapper(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # args[7] is stroke_color (the 8th parameter)
            new_args = list(args)
            if not use_outline:
                new_args[7] = None  # Set stroke_color to None if outline is disabled
            return func(*new_args, **kwargs)
        return wrapper
    
    # Apply the wrapper
    import movie
    movie.create_caption = create_caption_wrapper(movie.create_caption)
    
    # Standard parameters
    v_type = "9x16"
    subs_position = "center"
    highlight_color = None
    opacity = 0.0
    max_chars = 12
    
    # Process and add subtitles
    start_time = time.time()
    output_file, _ = add_subtitle(
        input_video,
        audio_path,
        v_type,
        subs_position,
        highlight_color,
        font_size,
        opacity,
        max_chars,
        f"#{text_color}",
        word_level_info,
        style_output_dir
    )
    
    # Restore original create_caption function
    movie.create_caption = original_create_caption
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Style {style_name} complete! Output: {output_file}")
    print(f"Processing time: {duration:.2f} seconds")
    
    return {
        "style_name": style_name,
        "output_file": output_file,
        "duration": duration,
        "settings": style_config
    }

async def test_all_styles(input_video, output_dir="subtitle_style_tests"):
    """Test all subtitle styles on a video"""
    print(f"Testing all subtitle styles on: {input_video}")
    
    # Ensure video exists
    if not os.path.exists(input_video):
        print(f"Error: Input video not found at {input_video}")
        return []
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Extract audio and transcribe only once
    audio_path = create_audio(input_video)
    model = load_whisper_model("small")
    word_level_info = transcribe_audio(model, audio_path)
    
    # Process all styles concurrently
    tasks = []
    for style_name, style_config in SUBTITLE_STYLES.items():
        task = asyncio.create_task(
            apply_subtitle_style(
                input_video,
                output_dir,
                style_name,
                style_config,
                model,
                audio_path,
                word_level_info
            )
        )
        tasks.append(task)
    
    # Wait for all styles to be processed
    results = await asyncio.gather(*tasks)
    
    print("\n=== Summary of Results ===")
    for result in results:
        print(f"Style: {result['style_name']}")
        print(f"Output: {result['output_file']}")
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Settings: {result['settings']}")
        print("-" * 40)
    
    # Create comparison video
    comparison_path = create_comparison_video(results, output_dir)
    if comparison_path:
        print(f"\n✅ Comparison video created: {comparison_path}")
    
    return results

def create_comparison_video(results, output_dir):
    """Create a grid video comparing all styles side by side"""
    try:
        # Check if we have results to compare
        valid_results = [r for r in results if r and os.path.exists(r['output_file'])]
        if len(valid_results) < 2:
            print("Not enough valid videos for comparison")
            return None
        
        comparison_path = os.path.join(output_dir, "subtitle_styles_comparison.mp4")
        
        # First create a text file with information about each style
        info_path = os.path.join(output_dir, "style_info.txt")
        with open(info_path, 'w') as f:
            for result in valid_results:
                style = result['style_name']
                settings = result['settings']
                f.write(f"Style: {style}\n")
                f.write(f"Font Size: {settings['font_size']}\n")
                f.write(f"Text Color: #{settings['text_color']}\n")
                f.write(f"Outline: {'Yes' if settings['use_outline'] else 'No'}\n")
                if settings['use_outline']:
                    f.write(f"Outline Color: #{settings['outline_color']}\n")
                f.write("\n")
        
        # Create the ffmpeg filter_complex command for grid layout
        if len(valid_results) <= 2:
            # 1x2 grid for 2 videos or fewer
            filter_complex = "[0:v][1:v]hstack=inputs=2[v]"
        elif len(valid_results) <= 4:
            # 2x2 grid for 3-4 videos
            filter_complex = "[0:v][1:v]hstack=inputs=2[top];"
            if len(valid_results) == 3:
                filter_complex += "[2:v][2:v]hstack=inputs=2[bottom];"
            else:
                filter_complex += "[2:v][3:v]hstack=inputs=2[bottom];"
            filter_complex += "[top][bottom]vstack=inputs=2[v]"
        else:
            # 3x2 grid for 5-6 videos
            filter_complex = "[0:v][1:v]hstack=inputs=2[top];"
            filter_complex += "[2:v][3:v]hstack=inputs=2[middle];"
            if len(valid_results) == 5:
                filter_complex += "[4:v][4:v]hstack=inputs=2[bottom];"
            else:
                filter_complex += "[4:v][5:v]hstack=inputs=2[bottom];"
            filter_complex += "[top][middle][bottom]vstack=inputs=3[v]"
        
        # Create the ffmpeg command
        cmd = ["ffmpeg", "-y"]
        
        # Add input files
        for result in valid_results:
            cmd.extend(["-i", result['output_file']])
        
        # Add filter complex for grid layout
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]", 
            # Use the audio from the first video
            "-map", "0:a",
            # Set output encoding parameters
            "-c:v", "libx264", 
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            # Set a consistent higher FPS
            "-r", "60",
            comparison_path
        ])
        
        # Run the command
        print("Creating comparison video...")
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
        # Verify the output exists
        if os.path.exists(comparison_path) and os.path.getsize(comparison_path) > 0:
            return comparison_path
        else:
            print("Failed to create comparison video")
            return None
            
    except Exception as e:
        print(f"Error creating comparison video: {e}")
        return None

async def test_custom_style(
    input_video,
    output_dir="subtitle_style_tests/custom",
    font_size=7,
    text_color="FFFF00",
    use_outline=True,
    outline_color="000000"
):
    """Test a custom subtitle style on a video"""
    style_config = {
        "font_size": int(font_size),
        "text_color": text_color,
        "use_outline": use_outline,
        "outline_color": outline_color
    }
    
    result = await apply_subtitle_style(
        input_video,
        output_dir,
        "custom",
        style_config
    )
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test various subtitle styles")
    parser.add_argument("--input-video", default="output/temp/stacked_mobile_highlight_9.mp4", 
                        help="Path to input video file")
    parser.add_argument("--output-dir", default="subtitle_style_tests", 
                        help="Directory to save output files")
    parser.add_argument("--test-all", action="store_true", 
                        help="Test all predefined styles")
    parser.add_argument("--font-size", type=int, default=24, 
                        help="Font size (percentage of video height)")
    parser.add_argument("--text-color", default="FFFF00", 
                        help="Color of subtitle text (hex without #)")
    parser.add_argument("--use-outline", action="store_true", default=True,
                        help="Whether to use text outline")
    parser.add_argument("--no-outline", action="store_false", dest="use_outline",
                        help="Disable text outline")
    parser.add_argument("--outline-color", default="000000", 
                        help="Color for text outline if enabled (hex without #)")
    
    args = parser.parse_args()
    
    if args.test_all:
        asyncio.run(test_all_styles(args.input_video, args.output_dir))
    else:
        asyncio.run(test_custom_style(
            args.input_video,
            args.output_dir,
            args.font_size,
            args.text_color,
            args.use_outline,
            args.outline_color
        )) 