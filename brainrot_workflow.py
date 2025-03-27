#!/usr/bin/env python3
import asyncio
import os
import argparse
import random
import subprocess
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# Import modules
from downloader import VideoDownloader
from highlights import HighlightExtractor
from video_formatter import VideoFormatter
from movie import load_whisper_model, create_audio, transcribe_audio, add_subtitle
from test_subtitle_styles import SUBTITLE_STYLES

class BrainrotWorkflow:
    def __init__(self, output_dir="output", temp_dir=None, subtitle_style="default"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        if temp_dir is None:
            temp_dir = self.output_dir / "temp"
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Store subtitle style
        self.subtitle_style = subtitle_style
        
        # Initialize components
        self.downloader = VideoDownloader(str(self.output_dir))
        self.highlight_extractor = HighlightExtractor(str(self.temp_dir))
        self.formatter = VideoFormatter(str(self.temp_dir))
        
        # Configure highlight extraction parameters
        self.highlight_extractor.min_clip_duration = 10
        self.highlight_extractor.max_clip_duration = 40
        self.highlight_extractor.silent_threshold = 0.04
        
        # Get system information for optimal performance settings
        cpu_count = os.cpu_count() or 4
        
        # Create semaphores for resource control with higher concurrency limits
        self.io_semaphore = asyncio.Semaphore(16)  # Increased from 8 to 16 for I/O bound operations
        self.cpu_semaphore = asyncio.Semaphore(cpu_count + 2)  # Added +2 as buffer for CPU operations
        
        # Significantly increase FFmpeg parallelism since most bottlenecks are I/O bound rather than CPU bound
        # FFmpeg processes can run in parallel with less resource contention than previously allowed
        self.ffmpeg_semaphore = asyncio.Semaphore(min(cpu_count * 3, 24))  # Triple capacity, up to 24 concurrent processes
        
        # Create larger executor pools for better throughput
        self.process_pool = ProcessPoolExecutor(max_workers=min(cpu_count, 6))  # Increased from 4 to 6
        self.thread_pool = ThreadPoolExecutor(max_workers=32)  # Doubled from 16 to 32
        
        print(f"BrainrotWorkflow initialized with output_dir={output_dir}, temp_dir={temp_dir}")
        print(f"System has {cpu_count} CPUs, configured for optimal parallel processing")

    async def run_subprocess(self, cmd, check=True, timeout=300):
        """Run a subprocess asynchronously with timeout"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
            if check and process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Command failed with code {process.returncode}: {error_msg}")
            return process.returncode, stdout, stderr
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            raise Exception(f"Command timed out after {timeout} seconds")

    async def download_video(self, url):
        """Download video from YouTube"""
        print("\n=== STEP 1: DOWNLOADING VIDEO ===")
        input_video = self.downloader.download_youtube(url)
        if not input_video:
            raise Exception("Failed to download video")
        print(f"✅ Downloaded video to: {input_video}")
        return input_video

    async def extract_highlights(self, input_video):
        """Extract highlights from video"""
        print("\n=== STEP 2: EXTRACTING HIGHLIGHTS ===")
        print(f"Extracting highlights with settings:")
        print(f"  - Min duration: {self.highlight_extractor.min_clip_duration}s")
        print(f"  - Max duration: {self.highlight_extractor.max_clip_duration}s")
        print(f"  - Silent threshold: {self.highlight_extractor.silent_threshold}")
        
        highlight_clips = await self.highlight_extractor.extract_highlights_async(input_video)
        if not highlight_clips or len(highlight_clips) == 0:
            raise Exception("No highlight clips were extracted")
        print(f"✅ Extracted {len(highlight_clips)} highlight clips")
        return highlight_clips

    async def format_for_mobile_async(self, video_path, clip_index):
        """Format a video for mobile viewing asynchronously"""
        clip_basename = Path(video_path).stem
        output_filename = f"mobile_highlight_{clip_index}.mp4"
        print(f"Formatting clip {clip_index} for mobile viewing: {clip_basename}")
        formatted_clip = await asyncio.to_thread(
            self.formatter.format_for_mobile,
            str(video_path),
            output_filename
        )
        return formatted_clip
            
    async def find_background_video(self, specified_path=None, use_dynamic=False):
        """Find an appropriate background video
        
        Args:
            specified_path: Specific path to a background video file
            use_dynamic: If True, randomly select a background for each clip
        """
        # First, set the dynamic background flag as a class attribute
        self.use_dynamic_background = use_dynamic
        
        # Handle cases where specified_path indicates dynamic selection
        if specified_path in ["dynamic", "@assets"]:
            self.use_dynamic_background = True
            specified_path = None
            print(f"🎲 Using dynamic background selection from assets folder")
        
        # For non-dynamic, specific background
        if specified_path and os.path.exists(specified_path) and specified_path not in ["dynamic", "@assets"]:
            self.background_videos = [specified_path]
            print(f"Using specific background video: {specified_path}")
            return specified_path
            
        # Look for background videos in assets directory
        possible_asset_paths = [
            Path("assets"),
            Path("./assets"),
            Path("../assets"),
            Path(os.path.expanduser("~/FR8/Brainrot Automacion/assets"))
        ]
        
        assets_dir = None
        for asset_path in possible_asset_paths:
            if asset_path.exists() and asset_path.is_dir():
                assets_dir = asset_path
                break
                
        if not assets_dir:
            raise Exception("Could not find assets directory")
            
        # Find all video files in assets directory
        background_videos = []
        for ext in ["mp4", "mov", "avi"]:
            background_videos.extend([str(f) for f in assets_dir.glob(f"*.{ext}")])
            
        if not background_videos:
            raise Exception("No suitable background videos found in assets directory")
            
        # Save all background videos for dynamic selection later
        self.background_videos = background_videos
        
        # List available backgrounds
        print(f"Found {len(background_videos)} background videos in assets folder:")
        for i, bg in enumerate(background_videos):
            print(f"  {i+1}. {Path(bg).name}")
        
        # For dynamic backgrounds, we still return one (it will be re-selected per clip)
        bg_video = random.choice(background_videos)
        print(f"✅ Selected initial background video: {bg_video}")
        if self.use_dynamic_background:
            print("🎲 Using dynamic background mode: random background for each clip")
        
        return bg_video

    async def _extract_audio(self, video_path):
        """Extract audio from video asynchronously with optimized settings"""
        try:
            # Create an optimized output filename
            audio_path = str(self.temp_dir / f"{Path(video_path).stem}.mp3")
            
            # Use optimized FFmpeg command for audio extraction
            # Lower quality (128k) is sufficient for speech recognition
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",  # No video
                "-c:a", "libmp3lame",  # Use MP3 encoding which is faster than AAC
                "-q:a", "4",  # Use quality-based VBR encoding (faster than CBR)
                "-ac", "1",  # Convert to mono (sufficient for speech, faster processing)
                audio_path
            ]
            
            async with self.io_semaphore:  # Use I/O semaphore instead of FFmpeg semaphore
                await self.run_subprocess(cmd)
                
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                print(f"Successfully extracted audio to: {audio_path}")
                return audio_path
            else:
                print(f"⚠️ Failed to extract audio: output file is empty or missing")
                return None
                
        except Exception as e:
            print(f"⚠️ Error extracting audio: {e}")
            return None
    
    async def _transcribe_audio(self, model, audio_path):
        """Transcribe audio with more efficient resource utilization and parallelism"""
        try:
            print(f"Transcribing audio: {audio_path}")
            
            # Use a thread pool to run the CPU-intensive transcription
            # with bounded timeout to prevent hanging
            async with self.cpu_semaphore:  # Limit concurrent transcriptions to avoid memory issues
                result = await asyncio.wait_for(
                    asyncio.to_thread(transcribe_audio, model, audio_path),
                    timeout=120  # 2-minute timeout for transcription
                )
            
            # Validate result
            if not result:
                print("⚠️ Transcription returned no results")
                return [{"word": "TRANSCRIPTION EMPTY", "start": 0.0, "end": 5.0}]
            
            # Make sure result is a list
            if not isinstance(result, list):
                print(f"⚠️ Expected list but got {type(result)}")
                return [{"word": "TRANSCRIPTION TYPE ERROR", "start": 0.0, "end": 5.0}]
            
            # Make sure we have at least one item
            if len(result) == 0:
                print("⚠️ Transcription returned empty list")
                return [{"word": "TRANSCRIPTION EMPTY LIST", "start": 0.0, "end": 5.0}]
            
            # Success - process in chunks for more efficient memory usage
            processed_results = []
            chunk_size = 100  # Process in chunks of 100 words
            
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i+chunk_size]
                processed_results.extend(chunk)
                
                # Yield control back to event loop periodically
                if i + chunk_size < len(result):
                    await asyncio.sleep(0)
            
            return processed_results
            
        except asyncio.TimeoutError:
            print("⚠️ Transcription timed out after 2 minutes")
            return [{"word": "TRANSCRIPTION TIMEOUT", "start": 0.0, "end": 5.0}]
        except Exception as e:
            print(f"⚠️ Transcription failed with error: {e}")
            import traceback
            traceback.print_exc()
            return [{"word": "TRANSCRIPTION FAILED", "start": 0.0, "end": 5.0}]

    async def stack_videos_async(self, main_clip, background_clip, duration):
        """Optimized stacking of videos with better parallelism and faster encoding"""
        clip_basename = Path(main_clip).stem
        clip_index = clip_basename.split('_')[-1] if '_' in clip_basename else '0'
        output_filename = f"stacked_mobile_highlight_{clip_index}.mp4"
        output_path = self.temp_dir / output_filename
        
        # Get main clip dimensions using asyncio
        probe_cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "v:0", 
            "-show_entries", "stream=width,height", 
            "-of", "csv=p=0", 
            str(main_clip)
        ]
        _, stdout, _ = await self.run_subprocess(probe_cmd)
        
        main_width, main_height = map(int, stdout.decode().strip().split(','))
        
        # Calculate dimensions for stacking
        target_width = 1080
        main_target_height = min(int(main_height * (target_width / main_width)), int(1920 * 0.35))
        main_target_height = max(main_target_height, int(1920 * 0.25))  # At least 25% of height
        main_target_height = self.ensure_even_dimensions(target_width, main_target_height)[1]
        
        if background_clip and os.path.exists(background_clip):
            # Run two FFmpeg operations in parallel
            main_scaled = self.temp_dir / f"main_scaled_highlight_{clip_index}.mp4"
            gradient = self.temp_dir / f"gradient_highlight_{clip_index}.mp4"
            
            # Create commands with optimized settings
            main_scale_cmd = [
                "ffmpeg", "-y",
                "-i", str(main_clip),
                "-vf", f"scale={target_width}:{main_target_height}:force_original_aspect_ratio=disable,setsar=1:1",
                "-c:v", "libx264", "-crf", "24", "-preset", "veryfast",  # Use veryfast preset
                "-tune", "fastdecode",  # Optimize for faster decoding
                "-c:a", "aac", "-b:a", "128k",  # Reduced audio bitrate
                str(main_scaled)
            ]
            
            gradient_height = 4
            gradient_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x333333:s=1080x{gradient_height}:d={duration}:r=30",
                "-c:v", "libx264", "-crf", "24", "-preset", "veryfast",
                str(gradient)
            ]
            
            # Run both in parallel
            tasks = [
                self._run_ffmpeg_with_semaphore(main_scale_cmd),
                self._run_ffmpeg_with_semaphore(gradient_cmd)
            ]
            
            # Wait for both to finish
            await asyncio.gather(*tasks)
            
            # Now stack the videos with optimized settings
            stack_cmd = [
                "ffmpeg", "-y",
                "-i", str(main_scaled),
                "-i", str(gradient),
                "-i", str(background_clip),
                "-filter_complex", "[0:v][1:v][2:v]vstack=inputs=3[v]",
                "-map", "[v]",
                "-map", "0:a",
                "-c:v", "libx264", "-crf", "24", "-preset", "veryfast",
                "-tune", "fastdecode",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",  # Optimize for web streaming
                str(output_path)
            ]
            
            await self._run_ffmpeg_with_semaphore(stack_cmd)
            
            if output_path.exists():
                return str(output_path)
        
        # Fallback to single-pass solution with optimized settings
        print(f"⚠️ Using fallback method for clip {clip_index}")
        pad_cmd = [
            "ffmpeg", "-y",
            "-i", str(main_clip),
            "-vf", f"scale={target_width}:{main_target_height},pad={target_width}:1920:0:0:color=black",
            "-c:v", "libx264", "-crf", "24", "-preset", "veryfast",
            "-tune", "fastdecode",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path)
        ]
        
        await self._run_ffmpeg_with_semaphore(pad_cmd)
        return str(output_path)

    async def _run_ffmpeg_with_semaphore(self, cmd, timeout=300):
        """Helper method to run ffmpeg with semaphore protection and optimized timeout handling
        
        This uses a streamlined approach with timeouts and better error handling.
        """
        try:
            async with self.ffmpeg_semaphore:
                # Add nice priority for better system responsiveness
                # Use nice on Unix systems to reduce priority slightly
                if os.name != 'nt':  # Not Windows
                    cmd = ["nice", "-n", "10"] + cmd
                    
                # Set specific timeout for this process
                return await asyncio.wait_for(
                    self.run_subprocess(cmd, check=False),  # Don't throw exceptions
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            print(f"⚠️ FFmpeg command timed out after {timeout}s: {' '.join(cmd[:5])}...")
            return None, None, b"Timeout"
        except Exception as e:
            print(f"⚠️ Error running FFmpeg: {e}")
            return None, None, str(e).encode()

    def ensure_even_dimensions(self, width, height):
        """Ensure both width and height are even numbers, required by most video codecs"""
        width = int(width)
        height = int(height)
        if width % 2 != 0:
            width += 1
        if height % 2 != 0:
            height += 1
        return width, height

    async def get_video_duration(self, video_path):
        """Get the duration of a video asynchronously"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        async with self.ffmpeg_semaphore:
            _, stdout, _ = await self.run_subprocess(cmd)
        return float(stdout.decode().strip())

    async def add_subtitles_async(self, video_path, whisper_model, clip_index, wordlevel_info=None):
        """Add subtitles to video using pre-computed wordlevel info with selected style"""
        clip_basename = Path(video_path).stem
        # Create a unique output directory for this clip to avoid conflicts
        clip_output_dir = self.temp_dir / f"subtitled_{clip_index}"
        os.makedirs(clip_output_dir, exist_ok=True)
        
        if not wordlevel_info:
            print(f"⚠️ No transcription data for clip {clip_index}")
            return video_path
            
        try:
            # Get style configuration
            style_config = SUBTITLE_STYLES.get(self.subtitle_style, SUBTITLE_STYLES["default"])
            
            # Extract style parameters
            font_size = style_config.get("font_size", 24)
            text_color = style_config.get("text_color", "FFFF00")
            use_outline = style_config.get("use_outline", True)
            outline_color = style_config.get("outline_color", "000000") if use_outline else None
            
            # Config for subtitles
            v_type = "9x16"
            
            # Calculate suitable position
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(video_path)
            ]
            
            async with self.ffmpeg_semaphore:
                _, stdout, _ = await self.run_subprocess(probe_cmd)
            
            width, height = map(int, stdout.decode().strip().split(','))
            
            # Position subtitles at 40% from top
            subs_position = (width / 2, height * 0.4)
            
            # Try to add subtitles using the movie.py function
            try:
                # Use the color parameter passed from the style
                output_path, _ = add_subtitle(
                    video_path,
                    None,  # No need for audio path since we have wordlevel_info
                    v_type,
                    subs_position,
                    None,  # No highlight color
                    font_size,
                    0.0,  # No background
                    12,   # Max chars per line
                    f"#{text_color}",  # Add # to text color
                    wordlevel_info,
                    str(clip_output_dir)
                )
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return output_path
                else:
                    # Fallback to direct FFmpeg subtitle rendering
                    return await self.ffmpeg_subtitle_fallback(video_path, wordlevel_info, f"{clip_basename}_{clip_index}")
                    
            except Exception as e:
                print(f"⚠️ Error adding subtitles with movie.py: {e}")
                return await self.ffmpeg_subtitle_fallback(video_path, wordlevel_info, f"{clip_basename}_{clip_index}")
                
        except Exception as e:
            print(f"⚠️ Error processing subtitles: {e}")
            return video_path

    async def ffmpeg_subtitle_fallback(self, video_path, wordlevel_info, clip_basename):
        """Fallback method to add subtitles using FFmpeg directly with selected style"""
        print(f"Using FFmpeg fallback for subtitles with style: {self.subtitle_style}")
        
        # Get style configuration
        style_config = SUBTITLE_STYLES.get(self.subtitle_style, SUBTITLE_STYLES["default"])
        
        # Extract style parameters
        font_size = style_config.get("font_size", 24)
        text_color = style_config.get("text_color", "FFFF00")
        use_outline = style_config.get("use_outline", True)
        outline_color = style_config.get("outline_color", "000000") if use_outline else None
        
        # Create subtitle file
        subtitle_file = self.temp_dir / f"subs_{clip_basename}.srt"
        with open(subtitle_file, 'w') as f:
            for i, word in enumerate(wordlevel_info):
                f.write(f"{i+1}\n")
                start_time = self.format_srt_time(word["start"])
                end_time = self.format_srt_time(word["end"])
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{word['word']}\n\n")
                
        # Convert hex color to ffmpeg subtitle format (BBGGRR)
        r, g, b = tuple(int(text_color[i:i+2], 16) for i in (0, 2, 4))
        ffmpeg_color = f"&H{b:02X}{g:02X}{r:02X}&"
        
        # Convert outline color if needed
        if use_outline and outline_color:
            or_, og, ob = tuple(int(outline_color[i:i+2], 16) for i in (0, 2, 4))
            outline_ffmpeg_color = f"&H{ob:02X}{og:02X}{or_:02X}&"
            border_style = "3"  # Outlined and shadowed
        else:
            outline_ffmpeg_color = "&H000000&"  # Black
            border_style = "1"  # No outline
        
        # Add subtitles with FFmpeg - use unique output name
        output_path = self.output_dir / f"subtitled_{clip_basename}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={subtitle_file}:force_style='FontSize={font_size*2},PrimaryColour={ffmpeg_color},OutlineColour={outline_ffmpeg_color},BorderStyle={border_style}'",
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "copy",
            str(output_path)
        ]
        
        try:
            async with self.ffmpeg_semaphore:
                await self.run_subprocess(cmd)
            return str(output_path)
        except Exception as e:
            print(f"⚠️ FFmpeg subtitle fallback failed: {e}")
            return video_path

    def format_srt_time(self, seconds):
        """Format time in SRT format (HH:MM:SS,mmm)"""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = seconds % 60
        milliseconds = int((secs - int(secs)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{milliseconds:03d}"

    async def optimize_video(self, video_path, clip_index):
        """Optimize video for web sharing with faster encoding"""
        clip_basename = Path(video_path).stem
        # Ensure unique output filename using clip_index
        output_path = self.output_dir / f"optimized_brainrot_highlight_{clip_index}.mp4"
        
        cmd = [
            "ffmpeg", "-y", 
            "-i", str(video_path),
            "-movflags", "+faststart",  # Optimize for web streaming
            "-c:v", "libx264", "-crf", "24", "-preset", "veryfast",  # Faster encoding preset
            "-tune", "fastdecode",  # Optimize for decoding speed
            "-c:a", "aac", "-b:a", "128k",  # Reduced audio bitrate
            # Add thread count for parallel encoding
            "-threads", str(min(os.cpu_count() or 4, 8)),
            str(output_path)
        ]
        
        try:
            async with self.ffmpeg_semaphore:
                await self.run_subprocess(cmd)
            if output_path.exists() and output_path.stat().st_size > 0:
                return str(output_path)
        except Exception as e:
            print(f"⚠️ Error optimizing video: {e}")
        
        # If optimization fails, copy the original to the output with unique name
        fallback_path = self.output_dir / f"brainrot_highlight_{clip_index}.mp4"
        try:
            import shutil
            shutil.copy2(video_path, fallback_path)
            return str(fallback_path)
        except Exception as e:
            print(f"⚠️ Error copying video: {e}")
            return video_path

    async def process_highlight_clip(self, highlight_clip, background_video, whisper_model, clip_index):
        """Process a single highlight clip with improved robustness and parallelism"""
        try:
            print(f"\n--- Processing highlight clip {clip_index+1} ---")
            
            # Step 1: Create all tasks for this clip at once 
            # This allows for maximum utilization of resources in parallel
            
            # Format video for mobile (basic step that other tasks depend on)
            clip_name = f"highlight_{clip_index}"
            mobile_clip = await self.format_for_mobile_async(highlight_clip, clip_index)
            if not mobile_clip:
                print(f"❌ Failed to format clip for mobile, skipping")
                return None
            
            # Get duration (needed for background)
            duration = await self.get_video_duration(mobile_clip)
            
            # Create all independent tasks in parallel:
            # 1. Extract audio & transcribe
            # 2. Prepare background video
            # We can't optimize more than this without restructuring the dependency graph
            
            # Create and start all tasks concurrently using gather for compatibility
            audio_task = self._extract_audio(mobile_clip)
            background_task = self.prepare_background_async(background_video, duration, f"{clip_name}_{clip_index}")
            
            # Run tasks in parallel
            audio_path, background_result = await asyncio.gather(audio_task, background_task)
            
            # Process results for audio extraction
            wordlevel_info = [{"word": "NO TRANSCRIPTION", "start": 0.0, "end": 5.0}]
            if audio_path:
                try:
                    # Optimize transcription with shorter timeout and parallelized processing
                    wordlevel_info = await self._transcribe_audio(whisper_model, audio_path)
                    print(f"✅ Transcription complete with {len(wordlevel_info)} words")
                except Exception as e:
                    print(f"⚠️ Transcription exception: {e}")
                    wordlevel_info = [{"word": "TRANSCRIPTION ERROR", "start": 0.0, "end": 5.0}]
            
            # Process results for background
            background_clip, use_background = background_result if background_result else (None, False)
            
            # Steps that must be done sequentially after formatting, audio extraction, and background preparation:
            # 1. Stack videos
            # 2. Add subtitles 
            # 3. Optimize final video
            
            # Stack videos
            print(f"\n=== STEP 4: STACKING VIDEOS (Clip {clip_index+1}) ===")
            stacked_clip = await self.stack_videos_async(mobile_clip, background_clip if use_background else None, duration)
            if not stacked_clip:
                print(f"❌ Failed to stack videos, using mobile clip")
                stacked_clip = mobile_clip
            
            # Add subtitles (depends on stacked video)
            print(f"\n=== STEP 5: ADDING SUBTITLES (Clip {clip_index+1}) ===")
            subtitled_clip = await self.add_subtitles_efficient(stacked_clip, clip_index, wordlevel_info)
            
            # Final optimization (depends on subtitled video)
            print(f"\n=== STEP 6: OPTIMIZING (Clip {clip_index+1}) ===")
            final_clip = await self.optimize_video(subtitled_clip, clip_index)
            
            print(f"✅ Completed processing for clip {clip_index+1}: {final_clip}")
            return final_clip
            
        except Exception as e:
            print(f"❌ Error processing highlight clip {clip_index+1}: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    async def add_subtitles_efficient(self, video_path, clip_index, wordlevel_info):
        """More efficient subtitle addition using direct FFmpeg rendering with centered positioning"""
        if not wordlevel_info:
            print(f"⚠️ No transcription data for clip {clip_index}")
            return video_path
            
        try:
            # Get style configuration
            style_config = SUBTITLE_STYLES.get(self.subtitle_style, SUBTITLE_STYLES["default"])
            
            # Extract style parameters
            font_size = style_config.get("font_size", 24)
            text_color = style_config.get("text_color", "FFFF00")
            use_outline = style_config.get("use_outline", True)
            outline_color = style_config.get("outline_color", "000000") if use_outline else None
            
            # Create subtitle file directly as SSA/ASS format
            subtitle_file = self.temp_dir / f"subs_{clip_index}.ass"
            
            # Calculate video dimensions for proper positioning
            probe_cmd = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height", 
                "-of", "csv=p=0", 
                str(video_path)
            ]
            
            async with self.ffmpeg_semaphore:
                _, stdout, _ = await self.run_subprocess(probe_cmd)
            
            width, height = map(int, stdout.decode().strip().split(','))
            
            # Create the ASS subtitle file with styling
            with open(subtitle_file, 'w', encoding='utf-8') as f:
                # Write header
                f.write("[Script Info]\n")
                f.write(f"PlayResX: {width}\n")
                f.write(f"PlayResY: {height}\n")
                f.write("ScaledBorderAndShadow: yes\n\n")
                
                # Write styles - CENTER ALIGNMENT IS KEY HERE
                f.write("[V4+ Styles]\n")
                f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                
                # Convert hex colors to ASS format (AABBGGRR)
                primary_color = f"&H00{text_color[4:6]}{text_color[2:4]}{text_color[0:2]}&"
                outline_col = f"&H00{outline_color[4:6]}{outline_color[2:4]}{outline_color[0:2]}&" if outline_color else "&H000000&"
                
                # Create style line
                bold = 1 if style_config.get("bold", False) else 0
                outline_size = 1 if use_outline else 0
                shadow = 1 if use_outline else 0
                
                # Position in the MIDDLE - Alignment 5 = center middle of screen
                # Change from alignment 8 (top center) to 5 (middle center)
                # Adjust vertical position to be in middle of top portion
                top_section_height = int(height * 0.4)  # Top 40% of video
                margin_v = int(top_section_height * 0.5)  # Center within top section
                
                f.write(f"Style: Default,Arial,{font_size*2},{primary_color},&H00FFFFFF&,{outline_col},&H80000000&,{bold},0,0,0,100,100,0,0,1,{outline_size},{shadow},5,30,30,{margin_v},1\n\n")
                
                # Write events
                f.write("[Events]\n")
                f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                
                # Add each word as an event
                for i, word in enumerate(wordlevel_info):
                    start_time = self.format_ass_time(word["start"])
                    end_time = self.format_ass_time(word["end"])
                    text = word["word"].strip()
                    if text:  # Only add non-empty words
                        f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")
            
            # Add subtitles with FFmpeg - use unique output name
            output_path = self.temp_dir / f"subtitled_efficient_{clip_index}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"ass={subtitle_file}",
                "-c:v", "libx264", "-crf", "23", "-preset", "faster",
                "-c:a", "copy",
                str(output_path)
            ]
            
            async with self.ffmpeg_semaphore:
                await self.run_subprocess(cmd)
                
            if output_path.exists() and output_path.stat().st_size > 0:
                return str(output_path)
            else:
                print(f"⚠️ Subtitle rendering failed, using original video")
                return video_path
                
        except Exception as e:
            print(f"⚠️ Error adding subtitles efficiently: {e}")
            return video_path
            
    def format_ass_time(self, seconds):
        """Format time in ASS format (H:MM:SS.cc)"""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = seconds % 60
        centisecs = int((secs - int(secs)) * 100)
        return f"{hours}:{minutes:02d}:{int(secs):02d}.{centisecs:02d}"

    async def prepare_background_async(self, background_video, duration, clip_name):
        """Prepare background video asynchronously with truly random selection for each clip"""
        try:
            # For dynamic background mode, select a new random background for each clip
            if hasattr(self, 'use_dynamic_background') and self.use_dynamic_background:
                # Make sure we have background videos to choose from
                if hasattr(self, 'background_videos') and self.background_videos:
                    # Force selection of a truly random background for each clip
                    if len(self.background_videos) > 1:
                        # Don't reuse the previous background if possible
                        previous_bg = background_video
                        available_bgs = [bg for bg in self.background_videos if bg != previous_bg]
                        if available_bgs:
                            background_video = random.choice(available_bgs)
                        else:
                            background_video = random.choice(self.background_videos)
                    else:
                        background_video = self.background_videos[0]
                    
                    print(f"🎲 Selected random background for clip {clip_name}: {Path(background_video).name}")
            
            if not background_video or not os.path.exists(background_video):
                print(f"⚠️ No valid background video for clip {clip_name}")
                return None, False
            
            bg_filename = f"bg_{clip_name}.mp4"
            
            # Get video duration for random starting point
            try:
                video_duration = await self.get_video_duration(background_video)
            except Exception as e:
                print(f"⚠️ Unable to get background video duration: {e}")
                video_duration = None
            
            # Calculate a random start time if video is long enough
            start_time = 0
            if video_duration and video_duration > duration + 5:  # +5s buffer
                max_start = max(0, video_duration - duration - 5)  # -5s safety margin
                start_time = random.uniform(0, max_start)
                print(f"🎲 Starting background at {start_time:.2f}s (of {video_duration:.2f}s)")
            
            # Use thread pool for more efficient processing
            background_clip = await asyncio.to_thread(
                self.formatter.loop_subway_surfers,
                background_video,
                duration,
                bg_filename,
                start_time
            )
            
            if background_clip and os.path.exists(background_clip):
                print(f"✅ Prepared background video: {background_clip}")
                return background_clip, True
                
        except Exception as e:
            print(f"⚠️ Error preparing background: {e}")
            import traceback
            traceback.print_exc()
            
        return None, False

    async def process_video(self, url, subway_video_path=None, subtitle_config=None, use_dynamic_background=False):
        """Process a video through the complete Brainrot workflow"""
        start_time = time.time()
        final_outputs = []
        
        try:
            # Apply custom subtitle config if provided
            if subtitle_config:
                SUBTITLE_STYLES[self.subtitle_style] = subtitle_config
                print(f"Applied custom subtitle configuration to style: {self.subtitle_style}")
            
            # Set dynamic background flag if either parameter indicates it
            if subway_video_path in ["dynamic", "@assets"] or use_dynamic_background:
                use_dynamic_background = True
                print("🎲 Dynamic background mode enabled")
            
            # Step 1: Download video
            input_video = await self.download_video(url)
            
            # Step 2: Extract highlights
            highlight_clips = await self.extract_highlights(input_video)
            
            # Create more aggressively parallel batch processing
            cpu_count = os.cpu_count() or 4
            optimal_batch_size = max(3, min(cpu_count + 2, 8))  # More aggressive batching: CPU count + 2, up to 8
            
            print(f"Processing {len(highlight_clips)} clips with optimized parallelism...")
            
            # Step 3: Pre-load resources in parallel that will be shared across all clips
            print("\n=== PREPARING SHARED RESOURCES ===")
            
            # Load model and find background concurrently
            resource_tasks = [
                self._load_whisper_model_async("small"),
                self.find_background_video(subway_video_path, use_dynamic_background)
            ]
            whisper_model, background_video = await asyncio.gather(*resource_tasks)
            
            print(f"Using batch size of {optimal_batch_size} for maximum throughput")
            
            # Process all clips with improved scheduling
            all_tasks = []
            for i, clip in enumerate(highlight_clips):
                task = self.process_highlight_clip(clip, background_video, whisper_model, i)
                all_tasks.append(task)
            
            # Use dynamic batch scheduling for better load balancing
            results = []
            if len(all_tasks) > 3:  # If we have more than 3 clips
                # Process initial batch immediately to maximize utilization
                first_batch_size = min(optimal_batch_size, len(all_tasks))
                print(f"\n=== PROCESSING INITIAL BATCH (1/{(len(all_tasks) + optimal_batch_size - 1) // optimal_batch_size}) ===")
                first_batch = all_tasks[:first_batch_size]
                pending = all_tasks[first_batch_size:]
                
                # Start processing the first batch
                batch_tasks = [asyncio.create_task(task) for task in first_batch]
                
                # As tasks complete, add new ones to maintain optimal concurrency
                completed = []
                while batch_tasks:
                    # Wait for any task to complete
                    done, batch_tasks = await asyncio.wait(
                        batch_tasks, 
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Add completed tasks to results
                    for task in done:
                        result = task.result()
                        if result:
                            completed.append(result)
                    
                    # Add new tasks from pending list to maintain concurrency
                    while pending and len(batch_tasks) < optimal_batch_size:
                        next_task = pending.pop(0)
                        batch_tasks.add(asyncio.create_task(next_task))
                        print(f"Starting clip {len(completed) + len(batch_tasks)}/{len(all_tasks)}")
                
                results = completed
            else:
                # For small number of clips, process all at once
                results = await asyncio.gather(*all_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Task for clip {i+1} failed with error: {result}")
                elif result:
                    final_outputs.append(result)
            
            # Clean up temporary files
            print("\n=== CLEANING UP TEMPORARY FILES ===")
            await self._cleanup_temp_files()
            
            total_time = time.time() - start_time
            clips_per_minute = len(final_outputs) / (total_time / 60) if total_time > 0 else 0
            print(f"\n=== PROCESSING COMPLETE ===")
            print(f"Total time: {total_time:.2f}s ({clips_per_minute:.2f} clips/minute)")
            print(f"Processed {len(final_outputs)} highlight clips successfully")
            for i, output in enumerate(final_outputs):
                print(f"  {i+1}. {output}")
            
            return final_outputs
            
        except Exception as e:
            print(f"❌ Error in main workflow: {e}")
            import traceback
            traceback.print_exc()
            return final_outputs

    async def _load_whisper_model_async(self, model_size):
        """Load whisper model asynchronously without trying to await the model itself"""
        # Use asyncio.to_thread to load the model in a thread
        return await asyncio.to_thread(load_whisper_model, model_size)

    async def _cleanup_temp_files(self):
        """Clean up temporary files to save disk space"""
        try:
            import shutil
            # Only remove files with certain patterns
            for pattern in ['*.mp4', '*.wav', '*.ass', '*.srt']:
                for file in self.temp_dir.glob(pattern):
                    if file.is_file() and not file.name.startswith('optimized_'):
                        try:
                            os.remove(file)
                        except:
                            pass
            print("✅ Temporary files cleaned up")
        except Exception as e:
            print(f"⚠️ Error cleaning up temporary files: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Brainrot Video Workflow")
    parser.add_argument("--url", required=True, help="YouTube URL to download and process")
    parser.add_argument("--output-dir", default="output", help="Directory to save output files")
    parser.add_argument("--subway-video", help="Path to background video file")
    args = parser.parse_args()
    
    workflow = BrainrotWorkflow(output_dir=args.output_dir)
    await workflow.process_video(args.url, args.subway_video)

if __name__ == "__main__":
    try:
        print("Starting Brainrot Video Workflow...")
        asyncio.run(main())
        print("Workflow completed successfully!")
    except KeyboardInterrupt:
        print("\nWorkflow interrupted by user. Exiting...")
    except Exception as e:
        print(f"ERROR: Workflow execution failed: {e}")
        import traceback
        traceback.print_exc()