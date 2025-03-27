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

class BrainrotWorkflow:
    def __init__(self, output_dir="output", temp_dir=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        if temp_dir is None:
            temp_dir = self.output_dir / "temp"
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.downloader = VideoDownloader(str(self.output_dir))
        self.highlight_extractor = HighlightExtractor(str(self.temp_dir))
        self.formatter = VideoFormatter(str(self.temp_dir))
        
        # Configure highlight extraction parameters
        self.highlight_extractor.min_clip_duration = 10
        self.highlight_extractor.max_clip_duration = 40
        self.highlight_extractor.silent_threshold = 0.04
        
        # Create semaphores for resource control
        self.io_semaphore = asyncio.Semaphore(8)  # For I/O bound operations
        self.cpu_semaphore = asyncio.Semaphore(os.cpu_count())  # For CPU bound operations
        self.ffmpeg_semaphore = asyncio.Semaphore(4)  # Limit concurrent FFmpeg processes
        
        # Create executor pools
        self.process_pool = ProcessPoolExecutor(max_workers=min(os.cpu_count(), 4))
        self.thread_pool = ThreadPoolExecutor(max_workers=16)
        
        print(f"BrainrotWorkflow initialized with output_dir={output_dir}, temp_dir={temp_dir}")

    async def run_subprocess(self, cmd, check=True, timeout=300):
        """Run a subprocess asynchronously with timeout"""
        async with self.ffmpeg_semaphore:
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
        async with self.ffmpeg_semaphore:
            clip_basename = Path(video_path).stem
            output_filename = f"mobile_highlight_{clip_index}.mp4"
            print(f"Formatting clip {clip_index} for mobile viewing: {clip_basename}")
            formatted_clip = await asyncio.to_thread(
                self.formatter.format_for_mobile,
                str(video_path),
                output_filename
            )
            return formatted_clip
            
    async def find_background_video(self, specified_path=None):
        """Find an appropriate background video"""
        if specified_path and os.path.exists(specified_path):
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
            
        if background_videos:
            # Randomly select a background video
            bg_video = random.choice(background_videos)
            print(f"✅ Selected background video: {bg_video}")
            return bg_video
                    
        raise Exception("No suitable background videos found in assets directory")

    async def stack_videos_async(self, main_clip, background_clip, duration):
        """Stack main clip on top of background video asynchronously"""
        async with self.ffmpeg_semaphore:
            clip_basename = Path(main_clip).stem
            clip_index = clip_basename.split('_')[-1] if '_' in clip_basename else '0'
            output_filename = f"stacked_mobile_highlight_{clip_index}.mp4"
            output_path = self.temp_dir / output_filename
            
            # Get main clip dimensions
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
            main_target_height = main_target_height + (main_target_height % 2)  # Ensure even
            
            if background_clip and os.path.exists(background_clip):
                # Scale main video
                main_scaled = self.temp_dir / f"main_scaled_highlight_{clip_index}.mp4"
                main_scale_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(main_clip),
                    "-vf", f"scale={target_width}:{main_target_height}:force_original_aspect_ratio=disable,setsar=1:1",
                    "-c:v", "libx264", "-crf", "23",
                    "-c:a", "aac", "-b:a", "192k",
                    str(main_scaled)
                ]
                await self.run_subprocess(main_scale_cmd)
                
                # Create gradient separator
                gradient = self.temp_dir / f"gradient_highlight_{clip_index}.mp4"
                gradient_height = 4
                gradient_cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", f"color=c=0x333333:s=1080x{gradient_height}:d={duration}:r=30",
                    "-c:v", "libx264", "-crf", "23",
                    str(gradient)
                ]
                await self.run_subprocess(gradient_cmd)
                
                # Stack videos with gradient
                stack_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(main_scaled),
                    "-i", str(gradient),
                    "-i", str(background_clip),
                    "-filter_complex", "[0:v][1:v][2:v]vstack=inputs=3[v]",
                    "-map", "[v]",
                    "-map", "0:a",
                    "-c:v", "libx264", "-crf", "23",
                    "-c:a", "aac", "-b:a", "192k",
                    str(output_path)
                ]
                
                try:
                    await self.run_subprocess(stack_cmd)
                    return str(output_path)
                except Exception as e:
                    print(f"⚠️ Failed to stack videos: {e}")
            
            # Fallback to padding if stacking fails or no background
            pad_height = 1920 - main_target_height
            pad_cmd = [
                "ffmpeg", "-y",
                "-i", str(main_clip),
                "-vf", f"scale={target_width}:{main_target_height},pad={target_width}:1920:0:0:color=black",
                "-c:v", "libx264", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
            await self.run_subprocess(pad_cmd)
            return str(output_path)

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
        _, stdout, _ = await self.run_subprocess(cmd)
        return float(stdout.decode().strip())

    async def add_subtitles_async(self, video_path, whisper_model, clip_index, wordlevel_info=None):
        """Add subtitles to video using pre-computed wordlevel info"""
        clip_basename = Path(video_path).stem
        # Create a unique output directory for this clip to avoid conflicts
        clip_output_dir = self.temp_dir / f"subtitled_{clip_index}"
        os.makedirs(clip_output_dir, exist_ok=True)
        
        if not wordlevel_info:
            print(f"⚠️ No transcription data for clip {clip_index}")
            return video_path
            
        try:
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
            _, stdout, _ = await self.run_subprocess(probe_cmd)
            width, height = map(int, stdout.decode().strip().split(','))
            
            # Position subtitles at 40% from top
            subs_position = (width / 2, height * 0.4)
            
            # Try to add subtitles using the movie.py function
            try:
                output_path, _ = add_subtitle(
                    video_path,
                    None,  # No need for audio path since we have wordlevel_info
                    v_type,
                    subs_position,
                    "#FFFF00",  # Yellow highlight
                    12.0,       # Font size
                    0.0,        # No background
                    12,         # Max chars per line
                    "#FFFF00",  # Text color
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
        """Fallback method to add subtitles using FFmpeg directly"""
        print(f"Using FFmpeg fallback for subtitles")
        
        # Create subtitle file
        subtitle_file = self.temp_dir / f"subs_{clip_basename}.srt"
        with open(subtitle_file, 'w') as f:
            for i, word in enumerate(wordlevel_info):
                f.write(f"{i+1}\n")
                start_time = self.format_srt_time(word["start"])
                end_time = self.format_srt_time(word["end"])
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{word['word']}\n\n")
                
        # Add subtitles with FFmpeg - use unique output name
        output_path = self.output_dir / f"subtitled_{clip_basename}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={subtitle_file}:force_style='FontSize=24,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=3'",
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "copy",
            str(output_path)
        ]
        
        try:
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
        """Optimize video for web sharing with unique output name"""
        clip_basename = Path(video_path).stem
        # Ensure unique output filename using clip_index
        output_path = self.output_dir / f"optimized_brainrot_highlight_{clip_index}.mp4"
        
        cmd = [
            "ffmpeg", "-y", 
            "-i", str(video_path),
            "-movflags", "+faststart",
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ]
        
        try:
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
        """Process a single highlight clip through the entire pipeline"""
        try:
            print(f"\n--- Processing highlight clip {clip_index+1} ---")
            
            # Step 1: Start multiple tasks concurrently
            # - Format video for mobile
            # - Get video duration and prepare background
            # - Extract audio for later transcription
            clip_name = f"highlight_{clip_index}"
            mobile_task = asyncio.create_task(self.format_for_mobile_async(highlight_clip, clip_index))
            
            # Wait for mobile formatting to get duration
            mobile_clip = await mobile_task
            if not mobile_clip:
                print(f"❌ Failed to format clip for mobile, skipping")
                return None
                
            # Get duration and start background preparation
            duration = await self.get_video_duration(mobile_clip)
            
            # Start background preparation and audio extraction concurrently
            background_task = asyncio.create_task(self.prepare_background_async(background_video, duration, f"{clip_name}_{clip_index}"))
            audio_task = asyncio.create_task(asyncio.to_thread(create_audio, mobile_clip))
            
            # While background is being prepared, start transcription if audio is ready
            audio_path = await audio_task
            transcription_task = None
            if audio_path:
                transcription_task = asyncio.create_task(asyncio.to_thread(transcribe_audio, whisper_model, audio_path))
            
            # Wait for background preparation
            background_result = await background_task
            background_clip, use_background = background_result if background_result else (None, False)
            
            # Stack videos
            print(f"\n=== STEP 4: STACKING VIDEOS (Clip {clip_index+1}) ===")
            stacked_clip = await self.stack_videos_async(mobile_clip, background_clip if use_background else None, duration)
            if not stacked_clip:
                print(f"❌ Failed to stack videos, using mobile clip")
                stacked_clip = mobile_clip
            
            # Wait for transcription if it was started
            wordlevel_info = None
            if transcription_task:
                try:
                    wordlevel_info = await transcription_task
                    print(f"✅ Transcription complete with {len(wordlevel_info)} words")
                except Exception as e:
                    print(f"⚠️ Error in transcription: {e}")
                    wordlevel_info = [{"word": "TRANSCRIPTION FAILED", "start": 0.0, "end": 5.0}]
            else:
                wordlevel_info = [{"word": "NO AUDIO AVAILABLE", "start": 0.0, "end": 5.0}]
            
            # Add subtitles
            print(f"\n=== STEP 5: ADDING SUBTITLES (Clip {clip_index+1}) ===")
            subtitled_clip = await self.add_subtitles_async(stacked_clip, whisper_model, clip_index, wordlevel_info)
            
            # Optimize final video
            print(f"\n=== STEP 6: OPTIMIZING (Clip {clip_index+1}) ===")
            final_clip = await self.optimize_video(subtitled_clip, clip_index)
            
            print(f"✅ Completed processing for clip {clip_index+1}: {final_clip}")
            return final_clip
            
        except Exception as e:
            print(f"❌ Error processing highlight clip {clip_index+1}: {e}")
            return None

    async def prepare_background_async(self, background_video, duration, clip_name):
        """Prepare background video asynchronously"""
        if not background_video or not os.path.exists(background_video):
            return None, False
            
        try:
            bg_filename = f"bg_{clip_name}.mp4"
            background_clip = await asyncio.to_thread(
                self.formatter.loop_subway_surfers,
                background_video,
                duration,
                bg_filename
            )
            
            if background_clip and os.path.exists(background_clip):
                print(f"✅ Prepared background video: {background_clip}")
                return background_clip, True
                
        except Exception as e:
            print(f"⚠️ Error preparing background: {e}")
            
        return None, False

    async def process_video(self, url, subway_video_path=None):
        """Process a video through the complete Brainrot workflow"""
        start_time = time.time()
        final_outputs = []
        
        try:
            # Step 1: Download video
            input_video = await self.download_video(url)
            
            # Step 2: Extract highlights
            highlight_clips = await self.extract_highlights(input_video)
            
            # Step 3: Find background video
            background_video = await self.find_background_video(subway_video_path)
            
            # Step 4: Load Whisper model (shared across all clips)
            print("\nInitializing Whisper model for transcription...")
            whisper_model = load_whisper_model("small")
            
            # Step 5: Process each highlight clip concurrently
            tasks = []
            for i, clip in enumerate(highlight_clips):
                task = self.process_highlight_clip(clip, background_video, whisper_model, i)
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Task for clip {i+1} failed with error: {result}")
                elif result:
                    final_outputs.append(result)
            
            # Clean up temporary files
            print("\n=== CLEANING UP TEMPORARY FILES ===")
            
            total_time = time.time() - start_time
            print(f"\n=== PROCESSING COMPLETE ===")
            print(f"Total time: {total_time:.2f}s")
            print(f"Processed {len(final_outputs)} highlight clips successfully")
            for i, output in enumerate(final_outputs):
                print(f"  {i+1}. {output}")
            
            return final_outputs
            
        except Exception as e:
            print(f"❌ Error in main workflow: {e}")
            return final_outputs

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