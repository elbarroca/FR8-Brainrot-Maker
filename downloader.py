#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path

class VideoDownloader:
    """Module responsible for downloading YouTube videos using yt-dlp"""
    
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        # Keep track of download attempts
        self.max_retries = 3
    
    def download_youtube(self, url, output_filename="input.mp4"):
        """Download YouTube video using yt-dlp with retries and robust error handling"""
        output_path = self.output_dir / output_filename
        
        # Check if file already exists
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"Video already exists at {output_path} ({output_path.stat().st_size} bytes). Skipping download.")
            return output_path
            
        print(f"Downloading video from {url} to {output_path}")
        
        # Try multiple times in case of network issues
        for attempt in range(1, self.max_retries + 1):
            try:
                # Base command with format selection for better compatibility
                cmd = [
                    "yt-dlp",
                    url,
                    "-o", str(output_path),
                    "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                    "--merge-output-format", "mp4",
                    "--no-playlist",  # Avoid downloading playlists by accident
                    "--retries", "3"  # Internal retries by yt-dlp
                ]
                
                # Print command for debugging
                print(f"Running download command (attempt {attempt}/{self.max_retries}): {' '.join(cmd)}")
                
                # Run the command with output capture
                process = subprocess.run(cmd, check=True, capture_output=True, text=True)
                
                # Verify the file exists and has content
                if output_path.exists() and output_path.stat().st_size > 0:
                    print(f"Successfully downloaded video to {output_path} ({output_path.stat().st_size} bytes)")
                    return output_path
                else:
                    print(f"Warning: Download seemed to succeed but output file is missing or empty")
                    
                    # Check the output for clues
                    if process.stdout:
                        print(f"Command output: {process.stdout}")
                    if process.stderr:
                        print(f"Command errors: {process.stderr}")
                        
            except subprocess.CalledProcessError as e:
                print(f"Error downloading video (attempt {attempt}/{self.max_retries}): {e}")
                
                # Print command output for debugging
                if e.stdout:
                    print(f"Command output: {e.stdout}")
                if e.stderr:
                    print(f"Command errors: {e.stderr}")
                
                # Try a different format if we're not on the last attempt
                if attempt < self.max_retries:
                    print(f"Retrying with different format options...")
                    time.sleep(2)  # Brief pause before retrying
                    
                    # Try with simpler format selection on subsequent attempts
                    if attempt == 2:
                        cmd = [
                            "yt-dlp",
                            url,
                            "-o", str(output_path),
                            "--format", "best[height<=720]/best",  # Try lower quality
                            "--merge-output-format", "mp4"
                        ]
                    else:
                        cmd = [
                            "yt-dlp",
                            url,
                            "-o", str(output_path),
                            "--format", "worst",  # Just get anything that works
                            "--merge-output-format", "mp4"
                        ]
            
            # If we reached max retries and still failed
            if attempt == self.max_retries:
                print(f"All download attempts failed for {url}")
                
                # Last resort: try to get info about the video to see if it's available
                try:
                    info_cmd = ["yt-dlp", "--dump-json", "--skip-download", url]
                    info_result = subprocess.run(info_cmd, capture_output=True, text=True)
                    print(f"Video info check result: {'Success' if info_result.returncode == 0 else 'Failed'}")
                    if info_result.stdout:
                        print(f"Video appears to be available but downloading failed. Check URL format and permissions.")
                except Exception as info_error:
                    print(f"Could not verify video availability: {info_error}")
                
                return None
                
        # If we got here, all attempts failed
        return None

if __name__ == "__main__":
    # Example usage
    downloader = VideoDownloader("output")
    video_path = downloader.download_youtube("https://www.youtube.com/watch?v=OGtetvg2pS8")
    print(f"Downloaded to: {video_path}") 