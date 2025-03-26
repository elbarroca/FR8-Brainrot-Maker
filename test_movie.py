#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

# Import modules from the movie.py script
from movie import load_whisper_model, create_audio, transcribe_audio, add_subtitle

def test_movie(
    input_video="output/temp/highlight_input_1.mp4",
    output_dir="test_movie_output",
    font_size=7.0,
    text_color="white",
    max_chars=12
):
    """
    Test movie.py subtitle functionality with minimal parameters
    
    Args:
        input_video: Path to input video
        output_dir: Directory to save output files
        font_size: Font size as percentage of video height
        text_color: Color of subtitle text
        max_chars: Maximum characters per line
    """
    print(f"Testing movie subtitle pipeline with video: {input_video}")
    
    # Ensure input video exists
    if not os.path.exists(input_video):
        print(f"Error: Input video not found at {input_video}")
        return
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Extract audio from video
    print("Extracting audio from video...")
    audio_path = create_audio(input_video)
    if not audio_path:
        print("Failed to extract audio")
        return
    
    # Load whisper model for transcription
    print("Loading Whisper model...")
    model = load_whisper_model("small")
    
    # Transcribe the audio
    print("Transcribing audio...")
    word_level_info = transcribe_audio(model, audio_path)
    
    # IMPORTANT: Always use "center" for subs_position to keep only center subtitles
    v_type = "9x16"
    subs_position = "center"
    highlight_color = None
    opacity = 0.0
    
    # Process and add subtitles
    print("Adding subtitles to video...")
    output_file, _ = add_subtitle(
        input_video,
        audio_path,
        v_type,
        subs_position,  # This must be "center" to keep only center subtitles
        highlight_color,
        font_size,
        opacity,
        max_chars,
        text_color,
        word_level_info,
        output_dir
    )
    
    print(f"Processing complete! Output saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test movie.py subtitle functionality")
    parser.add_argument("--input-video", default="output/temp/highlight_input_1.mp4", 
                        help="Path to input video file")
    parser.add_argument("--output-dir", default="test_movie_output", 
                        help="Directory to save output files")
    parser.add_argument("--font-size", type=float, default=7.0, 
                        help="Font size (percentage of video height)")
    parser.add_argument("--text-color", default="white", 
                        help="Color of subtitle text")
    parser.add_argument("--max-chars", type=int, default=12, 
                        help="Maximum characters per line")
    
    args = parser.parse_args()
    
    test_movie(
        args.input_video,
        args.output_dir,
        args.font_size,
        args.text_color,
        args.max_chars
    ) 