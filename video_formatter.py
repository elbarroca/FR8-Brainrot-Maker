import subprocess
import os
import numpy as np
from pathlib import Path

class VideoFormatter:
    """Module responsible for video formatting operations using ffmpeg"""
    
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def format_for_mobile(self, input_video, output_filename=None):
        """Format video for mobile viewing in 9:16 aspect ratio without adding vertical black bars"""
        if output_filename is None:
            output_filename = f"{Path(input_video).stem}_mobile.mp4"
        output_path = self.output_dir / output_filename
        print(f"Formatting {input_video} for mobile viewing")
        
        try:
            # Get video dimensions
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(input_video)
            ]
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True, check=True)
            width, height = map(int, probe_result.stdout.strip().split(','))
            print(f"  Source dimensions: {width}x{height}")
            
            # Calculate dimensions for 1080px width while maintaining aspect ratio
            target_width = 1080
            new_height = int(height * (target_width / width))
            
            # Ensure height is even (required by most video codecs)
            if new_height % 2 != 0:
                new_height += 1
                
            print(f"  Scaling to: {target_width}x{new_height} (maintaining aspect ratio, height made even)")
            
            # Use a more sophisticated scaling approach to eliminate horizontal black bars
            # First scale to fill width, then crop any excess height if necessary
            cmd = [
                "ffmpeg",
                "-i", str(input_video),
                "-vf", f"scale={target_width}:{new_height},setsar=1:1",
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-movflags", "+faststart",  # Web optimized
                str(output_path)
            ]
            
            print(f"  Running ffmpeg command to format for mobile...")
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Successfully formatted video for mobile viewing: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error formatting video for mobile: {e}")
            print(f"  Command output: {e.stderr.decode() if e.stderr else 'No error output'}")
            return None
    
    def crop_for_vertical(self, input_video, output_filename=None):
        """Crop video for top-half placement in 9:16 vertical format"""
        print("Warning: Using mobile-friendly formatting instead of cropping")
        return self.format_for_mobile(input_video, output_filename)
    
    def face_centered_crop(self, input_video, output_filename=None):
        """Crop video with face-centered approach using YOLOv8 face detection"""
        print("Warning: Using mobile-friendly formatting instead of face-centered cropping")
        return self.format_for_mobile(input_video, output_filename)
    
    def get_video_duration(self, video_path):
        """Get duration of video in seconds"""
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            str(video_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    
    def loop_subway_surfers(self, subway_video, target_duration, output_filename=None):
        """Loop Subway Surfers video to match highlight duration"""
        if output_filename is None:
            output_filename = "bottom_clip.mp4"
        output_path = self.output_dir / output_filename
        print(f"Looping {subway_video} to match duration of {target_duration} seconds")
        
        try:
            # Get original video dimensions
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(subway_video)
            ]
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True, check=True)
            vid_width, vid_height = map(int, probe_result.stdout.strip().split(','))
            print(f"  Source dimensions: {vid_width}x{vid_height}")
            
            # Enhanced looping for smoother transitions with centered cropping
            # Focus on the center of the video (where the character typically runs)
            # Calculate crop parameters to keep center in view
            target_width = 1080
            
            # Use a centered crop approach
            crop_filter = f"scale={target_width*1.2}:-1:force_original_aspect_ratio=increase,crop={target_width}:ih:(iw-{target_width})/2:0"
            
            cmd = [
                "ffmpeg",
                "-stream_loop", "-1",
                "-i", str(subway_video),
                "-t", str(target_duration),
                "-vf", crop_filter,  # Center-focused crop
                "-c:v", "libx264", 
                "-crf", "22",
                "-preset", "fast",
                str(output_path)
            ]
            subprocess.run(cmd, check=True)
            print(f"Successfully created centered and looped video at {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error looping video: {e}")
            return None
    
    def stack_videos(self, top_video, bottom_video, output_filename="final_output.mp4"):
        """Stack two videos vertically into a single 9:16 video for mobile viewing"""
        output_path = self.output_dir / output_filename
        print(f"Stacking {top_video} and {bottom_video} vertically")
        
        try:
            # Get top video dimensions
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(top_video)
            ]
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True, check=True)
            top_width, top_height = map(int, probe_result.stdout.strip().split(','))
            print(f"  Top video dimensions: {top_width}x{top_height}")
            
            # Get bottom video dimensions
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(bottom_video)
            ]
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True, check=True)
            bottom_width, bottom_height = map(int, probe_result.stdout.strip().split(','))
            print(f"  Bottom video dimensions: {bottom_width}x{bottom_height}")
            
            # Target output size for mobile (9:16 aspect ratio)
            output_width = 1080
            output_height = 1920
            print(f"  Output dimensions: {output_width}x{output_height}")
            
            # Calculate the natural height for the top video while maintaining its aspect ratio
            # Ensure the width is exactly output_width (1080px)
            top_aspect_ratio = top_width / top_height
            natural_height = int(output_width / top_aspect_ratio)
            
            # Cap the height to ensure it doesn't take more than 2/3 of the screen
            max_top_height = int(output_height * 0.75)
            top_video_height = min(natural_height, max_top_height)
            
            # Ensure minimum height of 1/3 of the screen
            min_top_height = int(output_height * 0.35)
            top_video_height = max(top_video_height, min_top_height)
            
            # The bottom video gets the remaining space
            bottom_video_height = output_height - top_video_height
            
            print(f"  Top video height (adaptive): {top_video_height}px ({(top_video_height/output_height)*100:.1f}%)")
            print(f"  Bottom video height (fill): {bottom_video_height}px ({(bottom_video_height/output_height)*100:.1f}%)")
            
            # Create a gradient overlay between videos for smoother transition
            # Use a more sophisticated filter graph with overlay transition and border effect
            filter_complex = (
                # Scale the top video
                f"[0:v]scale={output_width}:{top_video_height}:force_original_aspect_ratio=1,"
                f"pad={output_width}:{top_video_height}:(ow-iw)/2:0[top];"
                
                # Scale the bottom video
                f"[1:v]scale={output_width}:{bottom_video_height}:force_original_aspect_ratio=1,"
                f"pad={output_width}:{bottom_video_height}:(ow-iw)/2:0[bottom];"
                
                # Create a 5px gradient overlay for transition between videos
                f"color=black:{output_width}:5:d=1[gradient];"
                
                # Add a subtle border effect to the top video
                f"[top]drawbox=x=0:y={top_video_height-2}:w={output_width}:h=2:color=white@0.3:t=fill[top_border];"
                
                # Stack the videos with the gradient in between
                f"[top_border][gradient][bottom]vstack=inputs=3[v]"
            )
            
            print("  Creating vertical stack with adaptive height distribution...")
            
            # Check if the top video has audio
            audio_cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(top_video)
            ]
            has_audio = True
            try:
                audio_result = subprocess.run(audio_cmd, stdout=subprocess.PIPE, text=True)
                has_audio = "audio" in audio_result.stdout
            except Exception:
                has_audio = False
            
            # Stack videos using the enhanced filter
            cmd = [
                "ffmpeg",
                "-i", str(top_video),
                "-i", str(bottom_video),
                "-filter_complex", filter_complex,
                "-map", "[v]"
            ]
            
            # Only map audio if the top video has it
            if has_audio:
                cmd.extend(["-map", "0:a"])
                print("  ✓ Including audio from top video")
            else:
                print("  ⚠️ No audio found in top video")
            
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",  # Better quality
                "-c:a", "aac",
                "-b:a", "192k",  # Better audio quality
                "-movflags", "+faststart",  # Web optimized
                "-metadata", "title=Brainrot Short Video",
                str(output_path)
            ])
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Successfully stacked videos into {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Error stacking videos: {e}")
            print(f"  Command output: {e.stderr.decode() if e.stderr else 'No error output'}")
            return None
    
    def optimize_video(self, input_video, output_filename="final_ready.mp4"):
        """Optimize video for social media platforms"""
        output_path = self.output_dir / output_filename
        print(f"Optimizing {input_video} for social media")
        
        try:
            # Enhanced optimization with better quality settings and metadata
            # Uses 2-pass encoding for better quality at similar file sizes
            
            # First pass
            pass1_cmd = [
                "ffmpeg",
                "-y",
                "-i", str(input_video),
                "-c:v", "libx264",
                "-preset", "slow",  # Better compression
                "-b:v", "3M",       # Target bitrate
                "-pass", "1",
                "-f", "null",
                os.devnull
            ]
            
            # Second pass
            pass2_cmd = [
                "ffmpeg",
                "-i", str(input_video),
                "-c:v", "libx264",
                "-preset", "slow",
                "-b:v", "3M",
                "-pass", "2",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",  # Web optimized
                "-metadata", "title=Brainrot Short Video",
                "-metadata", "comment=Created with Brainrot Automation",
                str(output_path)
            ]
            
            subprocess.run(pass1_cmd, check=True)
            subprocess.run(pass2_cmd, check=True)
            
            # Remove temporary files created by 2-pass encoding
            temp_files = ["ffmpeg2pass-0.log", "ffmpeg2pass-0.log.mbtree"]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            print(f"Successfully optimized video to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error optimizing video: {e}")
            return None

if __name__ == "__main__":
    # Example usage
    formatter = VideoFormatter("output")
    
    # Check if the video with subtitles exists
    input_video = Path("output/highlights_subbed.mp4")
    
    if input_video.exists():
        # Step 1: Crop for vertical
        top_clip = formatter.crop_for_vertical(input_video)
        
        if top_clip:
            # Step 2: Loop Subway Surfers (assuming the file exists)
            subway_video = Path("assets/subway_surfers.mp4")
            
            if subway_video.exists():
                duration = formatter.get_video_duration(top_clip)
                bottom_clip = formatter.loop_subway_surfers(subway_video, duration)
                
                if bottom_clip:
                    # Step 3: Stack videos
                    stacked_video = formatter.stack_videos(top_clip, bottom_clip)
                    
                    if stacked_video:
                        # Step 4: Optimize
                        final_video = formatter.optimize_video(stacked_video)
                        print(f"Final video created at: {final_video}")
            else:
                print("Subway Surfers video not found. Please provide a valid path.")
    else:
        print("Video with subtitles not found. Run subtitles.py first.") 