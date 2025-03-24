#!/usr/bin/env python3
import subprocess
import asyncio
import os
import re
import shutil
from pathlib import Path
import random

class HighlightExtractor:
    """Module responsible for extracting multiple highlight clips from videos using Auto-Editor"""
    
    def __init__(self, output_dir):
        """Initialize the HighlightExtractor with configurable parameters"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectory for highlights
        self.highlights_dir = self.output_dir / "highlights"
        self.highlights_dir.mkdir(exist_ok=True)
        
        # Highlight extraction parameters
        self.min_clip_duration = 10    # Minimum duration in seconds for highlight clips
        self.max_clip_duration = 40    # Maximum duration in seconds for highlight clips
        self.max_clips_per_video = 20  # Maximum number of clips to extract per video
        
        # Auto-Editor settings - Adjusted for better detection
        self.silent_threshold = 0.04   # Increased threshold for better silence detection (was 0.015)
        self.frame_margin = 1          # Reduced margin for more precise clip boundaries
        
        # Remove semaphore creation from constructor
        self._semaphore = None
        
        print(f"Initialized HighlightExtractor with output_dir={output_dir}")
    
    def get_video_id_from_path(self, video_path):
        """Extract a video ID or name from the path"""
        filename = Path(video_path).stem
        # Try to find YouTube ID pattern
        yt_id_match = re.search(r'[-\w]{11,}', filename)
        if yt_id_match:
            return yt_id_match.group(0)
        return filename
    
    def _check_auto_editor_options(self):
        """Check available options for auto-editor on this system"""
        try:
            # Get help output to determine valid options
            help_cmd = ["auto-editor", "--help"]
            help_result = subprocess.run(help_cmd, capture_output=True, text=True)
            help_text = help_result.stdout + help_result.stderr
            
            # Determine valid export options
            export_options = []
            if "--export" in help_text:
                export_match = re.search(r'--export.*?options: \[(.*?)\]', help_text, re.DOTALL)
                if export_match:
                    export_options = [opt.strip() for opt in export_match.group(1).replace(',', ' ').split()]
            
            # Default to 'default' if we can't determine or if help doesn't show options
            if not export_options:
                export_options = ["default"]
                
            # Check if specific options are available
            silent_threshold_supported = "--silent-threshold" in help_text
            quiet_threshold_supported = "--quiet-threshold" in help_text
            silent_speed_supported = "--silent-speed" in help_text
            frame_margin_supported = "--frame-margin" in help_text
            margin_supported = "--margin" in help_text
            min_clip_supported = "--min-clip-length" in help_text or "--min-clip" in help_text
            max_clip_supported = "--max-clip-length" in help_text or "--max-clip" in help_text
            
            # Check if clips export is supported
            clips_supported = "clips" in export_options
                
            return {
                "export_options": export_options,
                "silent_threshold_supported": silent_threshold_supported,
                "quiet_threshold_supported": quiet_threshold_supported,
                "silent_speed_supported": silent_speed_supported,
                "frame_margin_supported": frame_margin_supported,
                "margin_supported": margin_supported,
                "min_clip_supported": min_clip_supported,
                "max_clip_supported": max_clip_supported,
                "clips_supported": clips_supported,
                "help_text": help_text  # Store the help text for later reference
            }
        except Exception as e:
            print(f"Error checking auto-editor options: {e}")
            # Fall back to safe defaults
            return {
                "export_options": ["default"],
                "silent_threshold_supported": False,
                "quiet_threshold_supported": False,
                "silent_speed_supported": False,
                "frame_margin_supported": False,
                "margin_supported": False,
                "min_clip_supported": False,
                "max_clip_supported": False,
                "clips_supported": False,
                "help_text": ""  # Empty help text as fallback
            }
    
    def get_video_duration(self, video_path):
        """Get duration of video in seconds"""
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            str(video_path)
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return 0.0
    
    def _extract_clips_using_auto_editor(self, input_video, video_id):
        """Extract clips using auto-editor to detect active segments"""
        print(f"Extracting highlight clips from {input_video} using auto-editor")
        
        # Check auto-editor options
        options = self._check_auto_editor_options()
        
        # Choose export option (prefer 'clips' if available)
        export_option = "default"
        if "clips" in options["export_options"]:
            export_option = "clips"  # Prefer clips export option if available
        elif export_option not in options["export_options"]:
            export_option = options["export_options"][0]
        
        # Verify video has sufficient length to be split
        video_duration = self.get_video_duration(input_video)
        print(f"Video duration: {video_duration:.2f} seconds")
        
        if video_duration <= self.min_clip_duration:
            print(f"Video too short ({video_duration:.2f}s) to extract highlights. Using entire video.")
            output_path = self.highlights_dir / f"highlight_{video_id}_1.mp4"
            shutil.copy2(input_video, output_path)
            main_output_path = self.output_dir / output_path.name
            shutil.copy2(output_path, main_output_path)
            return [main_output_path]
        
        # Use direct Auto-Editor --export clips to generate multiple clips in one go
        if export_option == "clips":
            # Build command based on available options
            cmd = [
                "auto-editor",
                str(input_video),
                "--export", "clips",           # Export individual clips instead of one file
                "--output", str(self.highlights_dir / f"highlight_{video_id}"),
                "--no-open"                    # Don't open files after processing
            ]
            
            # Add options only if they are supported
            if options["silent_threshold_supported"]:
                cmd.extend(["--silent-threshold", str(self.silent_threshold)])
            elif options["quiet_threshold_supported"]:
                cmd.extend(["--quiet-threshold", str(self.silent_threshold)])
                
            if options["frame_margin_supported"]:
                cmd.extend(["--frame-margin", str(self.frame_margin)])
                
            if options["min_clip_supported"]:
                min_val = str(max(3, self.min_clip_duration))
                if "--min-clip-length" in options["help_text"]:
                    cmd.extend(["--min-clip-length", min_val])
                else:
                    cmd.extend(["--min-clip", min_val])
            
            if options["max_clip_supported"]:
                max_val = str(self.max_clip_duration)
                if "--max-clip-length" in options["help_text"]:
                    cmd.extend(["--max-clip-length", max_val])
                else:
                    cmd.extend(["--max-clip", max_val])
                    
            if options["silent_speed_supported"]:
                cmd.extend(["--video-speed", "1"])  # Keep real-time speed
            
            print(f"Running auto-editor command: {' '.join(cmd)}")
            
            try:
                # Run auto-editor to directly get multiple clips
                process = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Get all generated clips
                pattern = f"highlight_{video_id}_*.mp4"
                highlight_clips = list(self.highlights_dir.glob(pattern))
                
                if highlight_clips:
                    print(f"Auto-Editor created {len(highlight_clips)} clips directly")
                    
                    # Sort clips by duration (longest first) to prioritize better content
                    highlight_clips.sort(key=lambda clip: -self.get_video_duration(clip))
                    
                    # Limit the number of clips
                    if len(highlight_clips) > self.max_clips_per_video:
                        excess_clips = highlight_clips[self.max_clips_per_video:]
                        highlight_clips = highlight_clips[:self.max_clips_per_video]
                        
                        # Remove excess clips
                        for clip in excess_clips:
                            try:
                                os.remove(clip)
                            except Exception as e:
                                print(f"Error removing excess clip {clip}: {e}")
                    
                    # Copy clips to main output directory
                    output_clips = []
                    for clip in highlight_clips:
                        main_output_path = self.output_dir / clip.name
                        shutil.copy2(clip, main_output_path)
                        output_clips.append(main_output_path)
                    
                    # If no clips were produced, fall back to manual splitting
                    if not output_clips:
                        print("Auto-Editor didn't produce any clips. Falling back to manual splitting.")
                        return self._split_into_clips(input_video, video_id)
                    
                    return output_clips
                else:
                    print("Auto-Editor clips export didn't produce any clips, falling back to manual splitting")
                    return self._split_into_clips(input_video, video_id)
            except Exception as e:
                print(f"Error using auto-editor clips export: {e}")
                print("Falling back to manual splitting")
                return self._split_into_clips(input_video, video_id)
        
        # If clips export failed or not available, use regular auto-editor (create a single output and split)
        temp_output = self.highlights_dir / f"temp_highlights_{video_id}.mp4"
        
        # Base command without optional parameters
        cmd = [
            "auto-editor",
            str(input_video),
            "--export", export_option,
            "--output", str(temp_output),
            "--no-open"                    # Don't open files after processing
        ]
        
        # Add options only if they are supported
        if options["silent_threshold_supported"]:
            cmd.extend(["--silent-threshold", str(self.silent_threshold)])
        elif options["quiet_threshold_supported"]:
            cmd.extend(["--quiet-threshold", str(self.silent_threshold)])
            
        if options["frame_margin_supported"]:
            cmd.extend(["--frame-margin", str(self.frame_margin)])
            
        if options["silent_speed_supported"]:
            cmd.extend(["--video-speed", "1"])  # Keep real-time speed
        
        # Run with the base command
        try:
            print(f"Running auto-editor with fallback command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not temp_output.exists():
                print("Auto-editor did not create output file. Falling back to manual splitting.")
                return self._split_into_clips(input_video, video_id)
            
            # Get generated file duration
            processed_duration = self.get_video_duration(temp_output)
            print(f"Auto-editor generated file duration: {processed_duration:.2f}s")
            
            # If auto-editor didn't significantly reduce the video, force manual splitting
            if processed_duration > video_duration * 0.8:
                print("Auto-editor didn't significantly reduce video length. Forcing manual splitting.")
                return self._split_into_clips(input_video, video_id)
            
            # If auto-editor created a single file, split it into clips
            highlights = self._split_into_clips(temp_output, video_id)
            
            # Clean up temporary file
            if temp_output.exists():
                os.remove(temp_output)
            
            return highlights
            
        except Exception as e:
            print(f"Error running auto-editor: {e}")
            print("Falling back to manual splitting")
            return self._split_into_clips(input_video, video_id)
    
    def _split_into_clips(self, input_video, video_id):
        """Split a video into multiple clips with dynamic durations based on content"""
        print(f"Manually splitting {input_video} into smaller clips")
        duration = self.get_video_duration(input_video)
        
        if duration <= self.min_clip_duration:
            print(f"Video too short ({duration:.2f}s) to split. Using entire video.")
            output_path = self.highlights_dir / f"highlight_{video_id}_1.mp4"
            shutil.copy2(input_video, output_path)
            main_output_path = self.output_dir / output_path.name
            shutil.copy2(output_path, main_output_path)
            return [main_output_path]
        
        # Calculate number of clips with variety in clip length
        num_clips = min(self.max_clips_per_video, max(2, int(duration / 20)))
        
        # Create a list of varied clip durations between min and max
        random.seed(42)  # For reproducibility
        
        # Create varied clip lengths
        clip_lengths = []
        remaining_duration = duration
        
        for i in range(num_clips):
            # Last clip gets remaining time
            if i == num_clips - 1:
                if remaining_duration >= self.min_clip_duration:
                    clip_lengths.append(remaining_duration)
                else:
                    # Extend previous clip if last segment is too short
                    if clip_lengths:
                        clip_lengths[-1] += remaining_duration
                break
                
            # Generate varied clip length
            min_length = self.min_clip_duration
            max_length = min(self.max_clip_duration, remaining_duration * 0.5)
            
            if max_length <= min_length:
                # Not enough duration left for variety
                clip_lengths.append(remaining_duration)
                break
                
            # Get a random length between min and max, weighted toward the middle
            clip_length = random.uniform(min_length, max_length)
            clip_lengths.append(clip_length)
            remaining_duration -= clip_length
            
            # Stop if remaining duration is too short
            if remaining_duration < self.min_clip_duration:
                break
        
        # Ensure we have at least one clip
        if not clip_lengths:
            clip_lengths = [duration]
        
        print(f"Splitting {duration:.2f}s video into {len(clip_lengths)} clips with varied durations")
        print(f"Planned clip durations: {[round(d, 1) for d in clip_lengths]}")
 
        highlights = []
        index = 1
        start_time = 0
 
        # Split video into clips with varied durations
        for clip_length in clip_lengths:
            output_filename = f"highlight_{video_id}_{index}.mp4"
            output_path = self.highlights_dir / output_filename
 
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-ss", str(start_time),
                "-t", str(clip_length),
                "-c:v", "libx264", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
 
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                main_output_path = self.output_dir / output_filename
                shutil.copy2(output_path, main_output_path)
                highlights.append(main_output_path)
                print(f"Created highlight clip {index}: {output_path} ({clip_length:.2f}s)")
            except Exception as e:
                print(f"Error creating clip {index}: {e}")
 
            start_time += clip_length
            index += 1
 
        print(f"Successfully created {len(highlights)} clips with varied durations from {input_video}")
        return highlights
    
    async def extract_highlights_async(self, input_video):
        """Asynchronously extract highlights from a video, supporting multiple output clips"""
        video_path = Path(input_video)
        if not video_path.exists():
            print(f"Video file does not exist: {video_path}")
            return []
        
        print(f"Starting highlight extraction for {video_path}")
        
        # Initialize semaphore lazily when we're in an asyncio context
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent extractions
        
        try:
            # Get video ID for consistent naming
            video_id = self.get_video_id_from_path(video_path)
            
            # Use semaphore to limit concurrent extractions
            async with self._semaphore:
                # Run extraction in a thread pool
                return await asyncio.to_thread(
                    self._extract_clips_using_auto_editor,
                    str(video_path),
                    video_id
                )
        except Exception as e:
            print(f"Error in async highlight extraction: {e}")
            # Create a fallback clip if extraction fails completely
            fallback_path = self.highlights_dir / f"highlight_fallback.mp4"
            try:
                shutil.copy2(input_video, fallback_path)
                main_output_path = self.output_dir / fallback_path.name
                shutil.copy2(fallback_path, main_output_path)
                return [main_output_path]
            except Exception as copy_error:
                print(f"Error creating fallback clip: {copy_error}")
                return []
    
    async def batch_process_videos(self, video_paths):
        """Process multiple videos asynchronously with improved concurrency control"""
        tasks = []
        results = []
        
        async def process_with_semaphore(path):
            # Acquire semaphore to control concurrency
            async with self._semaphore:
                result = await self.extract_highlights_async(path)
                return result
        
        # Create tasks for all videos
        for path in video_paths:
            task = asyncio.create_task(process_with_semaphore(path))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten the list of highlights
        all_highlights = []
        for result in results:
            if isinstance(result, list):
                all_highlights.extend(result)
            else:
                # Log any errors
                print(f"Error in batch processing: {result}")
        
        return all_highlights

if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def main():
        extractor = HighlightExtractor("output")
        
        # Single video processing
        input_video = "input.mp4"
        if os.path.exists(input_video):
            highlight_clips = await extractor.extract_highlights_async(input_video)
            print(f"Extracted {len(highlight_clips)} highlight clips")
        
        # Example batch processing
        # video_paths = ["video1.mp4", "video2.mp4"]
        # all_clips = await extractor.batch_process_videos(video_paths)
        # print(f"Batch processing complete: {len(all_clips)} total clips")
    
    asyncio.run(main()) 