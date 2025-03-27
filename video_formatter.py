import subprocess
import os
import numpy as np
from pathlib import Path
import random  # DO NOT REMOVE THE RANDOM START

class VideoFormatter:
    """Module responsible for video formatting operations using ffmpeg"""
    
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def ensure_even_dimensions(self, width, height):
        """Ensure both width and height are even numbers, required by most video codecs"""
        width = int(width)
        height = int(height)
        if width % 2 != 0:
            width += 1
        if height % 2 != 0:
            height += 1
        return width, height
    
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
                "-of", "csv=p=0"
            ]
            result = subprocess.run(probe_cmd + [str(input_video)], stdout=subprocess.PIPE, text=True, check=True)
            width, height = map(int, result.stdout.strip().split(','))
            print(f"Source dimensions: {width}x{height}")
            
            # Scale down to 1080px width, preserving aspect ratio.
            # ENSURE HEIGHT IS EVEN (this is the critical fix)
            target_width = 1080
            target_height = int(height * (target_width / width))
            target_width, target_height = self.ensure_even_dimensions(target_width, target_height)
            
            format_cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-vf", f"scale={target_width}:{target_height},setsar=1:1",
                "-c:v", "libx264", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            print(f"Running command: {' '.join(format_cmd)}")
            subprocess.run(format_cmd, check=True, capture_output=True)
            print(f"Formatted mobile video saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"Error formatting video: {e}")
            return None

    def format_asset_for_bottom(self, asset_video, crop_offset=100, output_filename=None):
        """
        Format asset video for bottom placement by cropping the top slightly.
        The asset video is already in mobile (9:16) format.
        A random start is applied (do not remove the random start) and the top is cropped by crop_offset pixels.
        """
        if output_filename is None:
            output_filename = f"{Path(asset_video).stem}_cropped.mp4"
        output_path = self.output_dir / output_filename
        print(f"Formatting asset video {asset_video} for bottom placement with top crop of {crop_offset}px")
        
        # Preserve random start as per original requirements.
        random_start = random.randint(0, 5)  # random start between 0 and 5 seconds
        
        # Crop filter: keep full width, reduce height by crop_offset, cropping from the top.
        crop_filter = f"crop=in_w:in_h-{crop_offset}:0:{crop_offset}"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(random_start),
            "-i", str(asset_video),
            "-vf", crop_filter,
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Cropped asset video saved to: {output_path}")
        return output_path
        
    def loop_subway_surfers(self, asset_video, target_duration, output_filename=None):
        """
        Prepares an asset video for use as background by cropping the top portion.
        
        Args:
            asset_video: Path to the asset video file
            target_duration: Duration in seconds the output video should be
            output_filename: Optional name for the output file
            
        Returns:
            Path to the processed video file
        """
        if output_filename is None:
            output_filename = f"bg_{Path(asset_video).stem}.mp4"
        output_path = self.output_dir / output_filename
        print(f"Preparing background video from {asset_video}")
        
        try:
            # Get video dimensions and duration
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0"
            ]
            result = subprocess.run(probe_cmd + [str(asset_video)], stdout=subprocess.PIPE, text=True, check=True)
            width, height = map(int, result.stdout.strip().split(','))
            print(f"Asset video dimensions: {width}x{height}")
            
            # Ensure width is 1080px for consistent stacking
            target_width = 1080
            
            # Calculate crop values - crop top 25% 
            crop_percent = 0.25
            crop_pixels = int(height * crop_percent)
            # Ensure crop value is even
            if crop_pixels % 2 != 0:
                crop_pixels += 1
                
            # For extra safety, use our even dimensions utility
            target_width, crop_pixels = self.ensure_even_dimensions(target_width, crop_pixels)
                
            print(f"Cropping {crop_pixels}px ({crop_percent*100}%) from the top of the video")
            
            # Apply a random start point (required feature)
            random_start = random.randint(0, 5)  # random start between 0 and 5 seconds
            print(f"Using random start point: {random_start}s")
            
            # Simple command to:
            # 1. Start at random position
            # 2. Scale to 1080px width
            # 3. Crop top 25%
            # 4. Ensure all dimensions are even (required by some codecs)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(random_start),
                "-i", str(asset_video),
                "-t", str(target_duration),
                "-vf", f"scale={target_width}:-2,crop=in_w:in_h-{crop_pixels}:0:{crop_pixels},setsar=1:1",
                "-an",  # Remove audio
                "-c:v", "libx264", "-crf", "23",
                "-pix_fmt", "yuv420p",  # Ensure compatibility
                str(output_path)
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Verify the output dimensions are even
            verify_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0",
                str(output_path)
            ]
            result = subprocess.run(verify_cmd, stdout=subprocess.PIPE, text=True, check=True)
            out_width, out_height = map(int, result.stdout.strip().split(','))
            
            # If dimensions are not even, fix them
            if out_width % 2 != 0 or out_height % 2 != 0:
                print(f"Output has odd dimensions ({out_width}x{out_height}), fixing...")
                fixed_path = self.output_dir / f"fixed_{output_filename}"
                fix_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(output_path),
                    "-vf", f"scale={out_width + (out_width % 2)}:{out_height + (out_height % 2)}",
                    "-c:v", "libx264", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-an",
                    str(fixed_path)
                ]
                subprocess.run(fix_cmd, check=True, capture_output=True)
                os.replace(fixed_path, output_path)  # Replace with fixed version
                print(f"Fixed dimensions to even values")
            
            print(f"Background video saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"Error preparing background video: {e}")
            return None