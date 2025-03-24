#!/usr/bin/env python3
import asyncio
import os
import argparse
from pathlib import Path
import time
import shutil
from concurrent.futures import ProcessPoolExecutor

# Import our modules
from downloader import VideoDownloader
from highlights import HighlightExtractor
from video_formatter import VideoFormatter
from movie import load_whisper_model, create_audio, transcribe_audio, add_subtitle

async def process_video(url, output_dir="output", subway_video_path=None, progress_queue=None):
    start_time = time.time()
    print(f"Starting processing for video: {url}")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    temp_dir = output_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # STEP 1: Download video
    print("\n=== STEP 1: DOWNLOADING VIDEO ===")
    downloader = VideoDownloader(str(output_dir))
    input_video = downloader.download_youtube(url)
    if not input_video:
        print("❌ Failed to download video, aborting process")
        return None
    print(f"✅ Downloaded video to: {input_video}")
    
    # STEP 2: Extract ALL highlights
    print("\n=== STEP 2: EXTRACTING HIGHLIGHTS ===")
    highlight_extractor = HighlightExtractor(str(temp_dir))
    highlight_extractor.min_clip_duration = 10
    highlight_extractor.max_clip_duration = 40
    highlight_extractor.silent_threshold = 0.04
    print(f"Extracting highlights with settings:")
    print(f"  - Min duration: {highlight_extractor.min_clip_duration}s")
    print(f"  - Max duration: {highlight_extractor.max_clip_duration}s")
    print(f"  - Silent threshold: {highlight_extractor.silent_threshold}")
    print(f"  - Max clips: No limit (extracting all possible highlights)")
    
    highlight_clips = await highlight_extractor.extract_highlights_async(input_video)
    if not highlight_clips or len(highlight_clips) == 0:
        print("❌ No highlight clips were extracted, aborting process")
        return None
    print(f"✅ Extracted {len(highlight_clips)} highlight clips")
    if progress_queue:
        await progress_queue.put({"type": "total", "count": len(highlight_clips)})
    
    print("\nInitializing Whisper model for transcription...")
    whisper_model = load_whisper_model("small")
    formatter = VideoFormatter(str(temp_dir))
    
    if not subway_video_path:
        possible_paths = [
            Path("assets/Subway Surfer Gameplay.mp4"),
            Path("./assets/Subway Surfer Gameplay.mp4"),
            Path("../assets/Subway Surfer Gameplay.mp4"),
            Path(os.path.expanduser("~/FR8/Brainrot Automacion/assets/Subway Surfer Gameplay.mp4"))
        ]
        for path in possible_paths:
            if path.exists():
                subway_video_path = str(path)
                print(f"✅ Found Subway Surfers video at: {subway_video_path}")
                break
        if not subway_video_path or not os.path.exists(subway_video_path):
            print("❌ ERROR: Subway Surfer Gameplay.mp4 not found!")
            print("Please place the video in the assets folder or specify it with --subway-video")
            return None
    
    final_outputs = []
    process_pool = ProcessPoolExecutor(max_workers=min(os.cpu_count(), 4))
    concurrency_limit = min(os.cpu_count() * 2, 16)
    semaphore = asyncio.Semaphore(concurrency_limit)
    io_semaphore = asyncio.Semaphore(concurrency_limit * 2)
    cpu_semaphore = asyncio.Semaphore(os.cpu_count())
    
    async def run_subprocess_async(cmd, check=True, timeout=300):
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
    
    async def process_highlight_clip(highlight_clip, clip_index):
        async with semaphore:
            clip_basename = Path(highlight_clip).stem
            print(f"\n--- Processing highlight clip {clip_index+1}/{len(highlight_clips)}: {clip_basename} ---")
            
            # STEP 3: Format for mobile
            print(f"\n=== STEP 3: FORMATTING FOR MOBILE (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 3, 
                    "highlight": clip_index+1,
                    "description": "Formatting for mobile"
                })
            mobile_filename = f"mobile_{clip_basename}.mp4"
            mobile_clip_path = str(temp_dir / mobile_filename)
            try:
                probe_cmd = [
                    "ffprobe", 
                    "-v", "error", 
                    "-select_streams", "v:0", 
                    "-show_entries", "stream=width,height", 
                    "-of", "csv=p=0", 
                    str(highlight_clip)
                ]
                _, stdout, _ = await run_subprocess_async(probe_cmd)
                src_width, src_height = map(int, stdout.decode().strip().split(','))
                print(f"Formatting {highlight_clip} for mobile viewing")
                print(f"  Source dimensions: {src_width}x{src_height}")
                target_width = 1080
                target_height = int(src_height * (target_width / src_width))
                if target_height % 2 != 0:
                    target_height += 1
                print(f"  Scaling to: {target_width}x{target_height}")
                format_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(highlight_clip),
                    "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,setsar=1:1",
                    "-c:v", "libx264", "-crf", "23",
                    "-c:a", "aac", "-b:a", "192k",
                    mobile_clip_path
                ]
                await run_subprocess_async(format_cmd)
                if os.path.exists(mobile_clip_path):
                    print(f"✅ Successfully formatted video for mobile viewing: {mobile_clip_path}")
                    mobile_clip = mobile_clip_path
                else:
                    print(f"❌ Failed to format clip for mobile, skipping to next clip")
                    return None
            except Exception as e:
                print(f"❌ Error formatting for mobile: {e}")
                return None
                
            print(f"✅ Formatted clip for mobile: {mobile_clip}")
            
            # STEP 4: Transcribe audio
            print(f"\n=== STEP 4: TRANSCRIBING AUDIO (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 4, 
                    "highlight": clip_index+1,
                    "description": "Transcribing audio"
                })
            # Offload audio extraction to a thread
            audio_path = await asyncio.to_thread(create_audio, mobile_clip)
            if not audio_path:
                print(f"⚠️ Failed to extract audio, creating empty transcription")
                wordlevel_info = [{"word": "NO AUDIO AVAILABLE", "start": 0.0, "end": 5.0}]
            else:
                try:
                    # Offload transcription to avoid blocking the event loop
                    wordlevel_info = await asyncio.to_thread(transcribe_audio, whisper_model, audio_path)
                    print(f"✅ Transcription complete with {len(wordlevel_info)} words")
                except Exception as e:
                    print(f"⚠️ Error transcribing audio: {e}")
                    wordlevel_info = [{"word": "TRANSCRIPTION FAILED", "start": 0.0, "end": 5.0}]
            
            # STEP 5: Prepare background
            print(f"\n=== STEP 5: PREPARING BACKGROUND (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 5, 
                    "highlight": clip_index+1,
                    "description": "Preparing background"
                })
            use_background = False
            background_clip = None
            if subway_video_path and os.path.exists(subway_video_path):
                duration_cmd = [
                    "ffprobe", 
                    "-v", "error", 
                    "-show_entries", "format=duration", 
                    "-of", "csv=p=0", 
                    mobile_clip
                ]
                _, stdout, _ = await run_subprocess_async(duration_cmd)
                clip_duration = float(stdout.decode().strip())
                background_filename = f"bg_{clip_basename}.mp4"
                background_clip_path = str(temp_dir / background_filename)
                try:
                    loop_cmd = [
                        "ffmpeg", "-y",
                        "-stream_loop", "-1",
                        "-i", subway_video_path,
                        "-t", str(clip_duration),
                        "-c:v", "libx264", "-crf", "23",
                        "-an",
                        background_clip_path
                    ]
                    await run_subprocess_async(loop_cmd)
                    if os.path.exists(background_clip_path):
                        print(f"✅ Prepared background video: {background_clip_path}")
                        background_clip = background_clip_path
                        use_background = True
                    else:
                        print(f"⚠️ Failed to prepare background video, falling back to black background")
                except Exception as e:
                    print(f"⚠️ Error preparing background: {e}")
                    print(f"⚠️ Falling back to black background")
            else:
                print(f"⚠️ No background video available, falling back to black background")
            
            # STEP 6: Add subtitles
            print(f"\n=== STEP 6: ADDING SUBTITLES (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 6, 
                    "highlight": clip_index+1,
                    "description": "Adding subtitles"
                })
            output_dir_subtitles = str(temp_dir / "subtitled")
            os.makedirs(output_dir_subtitles, exist_ok=True)
            # Offload subtitle processing to a thread
            subtitled_clip, _ = await asyncio.to_thread(add_subtitle,
                mobile_clip,
                audio_path,
                "9x16",
                "top",
                "#FFFF00",
                6.0,
                0.3,
                12,
                "#FFFFFF",
                wordlevel_info,
                output_dir_subtitles
            )
            if not subtitled_clip or not os.path.exists(subtitled_clip):
                print(f"⚠️ Failed to add subtitles, using clip without subtitles")
                subtitled_clip = mobile_clip
            else:
                print(f"✅ Added subtitles to clip: {subtitled_clip}")
            
            # STEP 7: Create final video
            print(f"\n=== STEP 7: CREATING FINAL VIDEO (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 7, 
                    "highlight": clip_index+1,
                    "description": "Creating final video"
                })
            final_filename = f"brainrot_{clip_basename}.mp4"
            final_path = output_dir / final_filename
            try:
                if use_background and background_clip:
                    probe_cmd = [
                        "ffprobe", 
                        "-v", "error", 
                        "-select_streams", "v:0", 
                        "-show_entries", "stream=width,height", 
                        "-of", "csv=p=0", 
                        str(subtitled_clip)
                    ]
                    _, stdout, _ = await run_subprocess_async(probe_cmd)
                    top_width, top_height = map(int, stdout.decode().strip().split(','))
                    print(f"Main video dimensions: {top_width}x{top_height}")
                    total_height = 1920
                    top_max_percent = 0.35
                    top_min_percent = 0.25
                    top_ideal_height = min(top_height, int(total_height * top_max_percent))
                    top_ideal_height = max(top_ideal_height, int(total_height * top_min_percent))
                    if top_ideal_height % 2 != 0:
                        top_ideal_height += 1
                    bottom_height = total_height - top_ideal_height
                    if bottom_height % 2 != 0:
                        bottom_height -= 1
                        top_ideal_height += 1
                    print(f"Optimized heights: Main={top_ideal_height}px, Subway={bottom_height}px")
                    top_video_scaled = temp_dir / f"top_scaled_{clip_basename}.mp4"
                    top_scale_cmd = [
                        "ffmpeg", "-y",
                        "-i", str(subtitled_clip),
                        "-vf", f"scale=1080:{top_ideal_height}:force_original_aspect_ratio=decrease,setsar=1:1",
                        "-c:v", "libx264", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k",
                        str(top_video_scaled)
                    ]
                    await run_subprocess_async(top_scale_cmd)
                    bottom_video_scaled = temp_dir / f"bottom_scaled_{clip_basename}.mp4"
                    probe_cmd = [
                        "ffprobe", 
                        "-v", "error", 
                        "-select_streams", "v:0", 
                        "-show_entries", "stream=width,height", 
                        "-of", "csv=p=0", 
                        str(background_clip)
                    ]
                    _, stdout, _ = await run_subprocess_async(probe_cmd)
                    bg_width, bg_height = map(int, stdout.decode().strip().split(','))
                    scale_factor = max(1080 / bg_width, bottom_height / bg_height)
                    scaled_height = int(bg_height * scale_factor)
                    y_offset = max(0, scaled_height - bottom_height)
                    new_height = bottom_height + scaled_height
                    bottom_scale_cmd = [
                        "ffmpeg", "-y",
                        "-i", str(background_clip),
                        "-vf", f"scale=1080:{new_height}:force_original_aspect_ratio=increase,crop=1080:{bottom_height}:0:{y_offset}",
                        "-c:v", "libx264", "-crf", "23",
                        "-an",
                        str(bottom_video_scaled)
                    ]
                    await run_subprocess_async(bottom_scale_cmd)
                    gradient = temp_dir / f"gradient_{clip_basename}.mp4"
                    gradient_cmd = [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"color=c=0x333333:s=1080x4:d=0.1:r=30",
                        "-c:v", "libx264", "-crf", "23",
                        str(gradient)
                    ]
                    await run_subprocess_async(gradient_cmd)
                    stack_cmd = [
                        "ffmpeg", "-y",
                        "-i", str(top_video_scaled),
                        "-i", str(gradient),
                        "-i", str(bottom_video_scaled),
                        "-filter_complex", "[0:v][1:v][2:v]vstack=inputs=3[v]",
                        "-map", "[v]",
                        "-map", "0:a",
                        "-c:v", "libx264", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k",
                        str(final_path)
                    ]
                    await run_subprocess_async(stack_cmd)
                    if final_path.exists() and final_path.stat().st_size > 0:
                        print(f"✅ Created stacked video: {final_path}")
                    else:
                        print(f"⚠️ Failed to create stacked video, falling back to subtitled clip only")
                        shutil.copy2(subtitled_clip, final_path)
                else:
                    print(f"⚠️ No background video available, using subtitled clip with black padding")
                    probe_cmd = [
                        "ffprobe", 
                        "-v", "error", 
                        "-select_streams", "v:0", 
                        "-show_entries", "stream=width,height", 
                        "-of", "csv=p=0", 
                        str(subtitled_clip)
                    ]
                    _, stdout, _ = await run_subprocess_async(probe_cmd)
                    top_width, top_height = map(int, stdout.decode().strip().split(','))
                    target_height = 1920
                    pad_height = target_height - top_height
                    if (top_height + pad_height) % 2 != 0:
                        pad_height += 1
                    print(f"Adding {pad_height}px of padding to reach 9:16 aspect ratio")
                    pad_cmd = [
                        "ffmpeg", "-y",
                        "-i", subtitled_clip,
                        "-vf", f"scale=1080:{top_height},pad=1080:{top_height+pad_height}:0:0:color=black",
                        "-c:v", "libx264", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k",
                        str(final_path)
                    ]
                    await run_subprocess_async(pad_cmd)
                    if not final_path.exists() or final_path.stat().st_size == 0:
                        print(f"⚠️ Failed to create padded video, using original clip")
                        shutil.copy2(subtitled_clip, final_path)
            except Exception as e:
                print(f"⚠️ Error creating final video: {e}")
                try:
                    shutil.copy2(subtitled_clip, final_path)
                except Exception as copy_error:
                    print(f"❌ Error copying subtitled clip: {copy_error}")
                    return None
            
            # STEP 8: Optimize final video
            print(f"\n=== STEP 8: OPTIMIZING VIDEO (Clip {clip_index+1}) ===")
            if progress_queue:
                await progress_queue.put({
                    "type": "step", 
                    "step": 8, 
                    "highlight": clip_index+1,
                    "description": "Optimizing video"
                })
            optimized_filename = f"optimized_brainrot_{clip_basename}.mp4"
            optimized_path = output_dir / optimized_filename
            try:
                optimize_cmd = [
                    "ffmpeg", "-y", 
                    "-i", str(final_path),
                    "-movflags", "+faststart",
                    "-c:v", "libx264", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    str(optimized_path)
                ]
                await run_subprocess_async(optimize_cmd)
                if optimized_path.exists() and optimized_path.stat().st_size > 0:
                    print(f"✅ Optimized final video: {optimized_path}")
                    if progress_queue:
                        await progress_queue.put({
                            "type": "completed",
                            "highlight": clip_index+1
                        })
                    return optimized_path
                else:
                    print(f"⚠️ Optimization failed, using unoptimized video")
                    if progress_queue:
                        await progress_queue.put({
                            "type": "completed",
                            "highlight": clip_index+1
                        })
                    return final_path
            except Exception as e:
                print(f"⚠️ Error during optimization: {e}")
                if progress_queue:
                    await progress_queue.put({
                        "type": "completed",
                        "highlight": clip_index+1
                    })
                return final_path
    
    print(f"\nProcessing {len(highlight_clips)} highlights with concurrency limit of {concurrency_limit}...")
    tasks = [asyncio.create_task(process_highlight_clip(clip, i)) for i, clip in enumerate(highlight_clips)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            print(f"❌ Task failed with error: {result}")
        elif result is not None:
            final_outputs.append(result)
    
    print("\n=== CLEANING UP INTERMEDIATE FILES ===")
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"✅ Removed temporary files")
    except Exception as e:
        print(f"⚠️ Error cleaning up temporary files: {e}")
    
    total_time = time.time() - start_time
    print(f"\n=== PROCESSING COMPLETE ===")
    print(f"Total time: {total_time:.2f}s")
    print(f"Processed {len(final_outputs)} highlight clips")
    for i, output in enumerate(final_outputs):
        print(f"  {i+1}. {output}")
    return final_outputs

async def main():
    parser = argparse.ArgumentParser(description="Brainrot Video Automation Pipeline")
    parser.add_argument("--url", help="YouTube URL to download and process")
    parser.add_argument("--output-dir", default="output", help="Directory to save output files")
    parser.add_argument("--subway-video", help="Path to Subway Surfers video file")
    args = parser.parse_args()
    if not args.url:
        parser.error("Please provide a YouTube URL with --url")
    await process_video(args.url, args.output_dir, args.subway_video)

if __name__ == "__main__":
    try:
        print("Starting Brainrot Video Automation Pipeline...")
        asyncio.run(main())
        print("Pipeline completed successfully!")
    except Exception as e:
        print(f"ERROR: Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()