#!/usr/bin/env python3
import subprocess
import asyncio
import os
import re
import shutil
import random
from pathlib import Path

class HighlightExtractor:
    """Module responsible for extracting multiple highlight clips from videos using Auto-Editor and active segment detection."""
    
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.highlights_dir = self.output_dir / "highlights"
        self.highlights_dir.mkdir(exist_ok=True)
        
        # Extraction parameters
        self.min_clip_duration = 10    # seconds
        self.max_clip_duration = 35    # seconds 
        self.max_clips_per_video = 88
        
        # Auto-Editor settings – tuned for silence/motion detection
        self.silent_threshold = 0.04   # base threshold
        self.frame_margin = 1          # precise cut boundaries
        
        self._semaphore = None
        print(f"Initialized HighlightExtractor with output_dir={output_dir}")
    
    def get_video_id_from_path(self, video_path):
        filename = Path(video_path).stem
        yt_id_match = re.search(r'[-\w]{11,}', filename)
        return yt_id_match.group(0) if yt_id_match else filename
    
    def _check_auto_editor_options(self):
        try:
            help_cmd = ["auto-editor", "--help"]
            help_result = subprocess.run(help_cmd, capture_output=True, text=True)
            help_text = help_result.stdout + help_result.stderr
            export_options = []
            if "--export" in help_text:
                export_match = re.search(r'--export.*?options: \[(.*?)\]', help_text, re.DOTALL)
                if export_match:
                    export_options = [opt.strip() for opt in export_match.group(1).replace(',', ' ').split()]
            if not export_options:
                export_options = ["default"]
            return {
                "export_options": export_options,
                "silent_threshold_supported": "--silent-threshold" in help_text,
                "quiet_threshold_supported": "--quiet-threshold" in help_text,
                "silent_speed_supported": "--silent-speed" in help_text,
                "frame_margin_supported": "--frame-margin" in help_text,
                "min_clip_supported": "--min-clip-length" in help_text or "--min-clip" in help_text,
                "max_clip_supported": "--max-clip-length" in help_text or "--max-clip" in help_text,
                "clips_supported": "clips" in export_options,
                "help_text": help_text
            }
        except Exception as e:
            print(f"Error checking auto-editor options: {e}")
            return {
                "export_options": ["default"],
                "silent_threshold_supported": False,
                "quiet_threshold_supported": False,
                "silent_speed_supported": False,
                "frame_margin_supported": False,
                "min_clip_supported": False,
                "max_clip_supported": False,
                "clips_supported": False,
                "help_text": ""
            }
    
    def get_video_duration(self, video_path):
        cmd = [
            "ffprobe", "-v", "error",
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
        print(f"Extracting highlight clips from {input_video} using auto-editor")
        options = self._check_auto_editor_options()
        export_option = "clips" if "clips" in options["export_options"] else options["export_options"][0]
        video_duration = self.get_video_duration(input_video)
        print(f"Video duration: {video_duration:.2f} seconds")
        
        if video_duration <= self.min_clip_duration:
            print(f"Video too short ({video_duration:.2f}s). Using entire video.")
            output_path = self.highlights_dir / f"highlight_{video_id}_1.mp4"
            shutil.copy2(input_video, output_path)
            main_output_path = self.output_dir / output_path.name
            shutil.copy2(output_path, main_output_path)
            return [main_output_path]
        
        # Build auto-editor command using available options.
        cmd = [
            "auto-editor", str(input_video),
            "--export", "clips",
            "--output", str(self.highlights_dir / f"highlight_{video_id}"),
            "--no-open"
        ]
        if options["silent_threshold_supported"]:
            cmd.extend(["--silent-threshold", str(self.silent_threshold)])
        elif options["quiet_threshold_supported"]:
            cmd.extend(["--quiet-threshold", str(self.silent_threshold)])
        if options["frame_margin_supported"]:
            cmd.extend(["--frame-margin", str(self.frame_margin)])
        if options["min_clip_supported"]:
            min_val = str(max(3, self.min_clip_duration))
            key = "--min-clip-length" if "--min-clip-length" in options["help_text"] else "--min-clip"
            cmd.extend([key, min_val])
        if options["max_clip_supported"]:
            max_val = str(self.max_clip_duration)
            key = "--max-clip-length" if "--max-clip-length" in options["help_text"] else "--max-clip"
            cmd.extend([key, max_val])
        if options["silent_speed_supported"]:
            cmd.extend(["--video-speed", "1"])
        
        print(f"Running auto-editor command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            pattern = f"highlight_{video_id}_*.mp4"
            clips = list(self.highlights_dir.glob(pattern))
            if clips:
                print(f"Auto-Editor produced {len(clips)} clip(s)")
                if len(clips) < 2:
                    print("Too few clips produced; auto-editor may not have detected enough active segments.")
                    # Fall back to active segment detection.
                    return self._split_using_active_segments(input_video, video_id)
                if len(clips) > self.max_clips_per_video:
                    for clip in clips[self.max_clips_per_video:]:
                        try:
                            os.remove(clip)
                        except Exception as e:
                            print(f"Error removing excess clip {clip}: {e}")
                    clips = clips[:self.max_clips_per_video]
                output_clips = []
                for clip in clips:
                    main_output_path = self.output_dir / clip.name
                    shutil.copy2(clip, main_output_path)
                    output_clips.append(main_output_path)
                return output_clips
            else:
                print("Auto-Editor produced no clips; falling back to active segment detection.")
                return self._split_using_active_segments(input_video, video_id)
        except Exception as e:
            print(f"Error with auto-editor: {e}")
            print("Falling back to active segment detection.")
            return self._split_using_active_segments(input_video, video_id)
    
    def _detect_active_segments(self, input_video):
        """Use ffmpeg silencedetect filter to determine active (non-silent) segments."""
        cmd = [
            "ffmpeg", "-i", str(input_video),
            "-af", "silencedetect=noise=-30dB:d=0.5",
            "-f", "null", "-"
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = process.stderr
        silences = []
        for line in output.splitlines():
            if "silence_start:" in line:
                try:
                    start = float(line.split("silence_start:")[1].strip())
                    silences.append(("start", start))
                except:
                    continue
            elif "silence_end:" in line:
                try:
                    end = float(line.split("silence_end:")[1].split(" |")[0].strip())
                    silences.append(("end", end))
                except:
                    continue
        silences.sort(key=lambda x: x[1])
        video_duration = self.get_video_duration(input_video)
        segments = []
        if not silences:
            segments.append((0, video_duration))
            return segments
        # Active segment before first silence
        if silences[0][0] == "start" and silences[0][1] > 0:
            segments.append((0, silences[0][1]))
        # Between silences
        for i in range(len(silences) - 1):
            if silences[i][0] == "end" and silences[i+1][0] == "start":
                segments.append((silences[i][1], silences[i+1][1]))
        # After last silence
        if silences[-1][0] == "end" and silences[-1][1] < video_duration:
            segments.append((silences[-1][1], video_duration))
        return segments
    
    def _split_using_active_segments(self, input_video, video_id):
        """Fallback: Use detected active segments to extract highlight clips."""
        print("Detecting active segments via silencedetect...")
        segments = self._detect_active_segments(input_video)
        valid_segments = [seg for seg in segments if (seg[1] - seg[0]) >= self.min_clip_duration]
        if not valid_segments:
            print("No active segments found with sufficient duration.")
            return []
        highlights = []
        index = 1
        for (start, end) in valid_segments:
            seg_duration = end - start
            # If segment is longer than max_clip_duration, split into variably sized subclips
            if seg_duration > self.max_clip_duration:
                # Generate variable clip durations between min and max
                current_pos = start
                while current_pos + self.min_clip_duration < end:
                    # Use variable clip lengths between min_clip_duration and max_clip_duration
                    # This creates more natural-feeling clip lengths
                    target_duration = min(
                        random.uniform(self.min_clip_duration, self.max_clip_duration),
                        end - current_pos  # Don't exceed segment end
                    )
                    
                    # Cap at max_clip_duration
                    target_duration = min(target_duration, self.max_clip_duration)
                    
                    output_filename = f"highlight_{video_id}_{index}.mp4"
                    output_path = self.highlights_dir / output_filename
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(input_video),
                        "-ss", str(current_pos),
                        "-t", str(target_duration),
                        "-c:v", "libx264", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k",
                        str(output_path)
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    main_output_path = self.output_dir / output_filename
                    shutil.copy2(output_path, main_output_path)
                    highlights.append(main_output_path)
                    index += 1
                    current_pos += target_duration
            else:
                output_filename = f"highlight_{video_id}_{index}.mp4"
                output_path = self.highlights_dir / output_filename
                duration = seg_duration
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(input_video),
                    "-ss", str(start),
                    "-t", str(duration),
                    "-c:v", "libx264", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k",
                    str(output_path)
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                main_output_path = self.output_dir / output_filename
                shutil.copy2(output_path, main_output_path)
                highlights.append(main_output_path)
                index += 1
        print(f"Extracted {len(highlights)} clip(s) using active segment detection.")
        return highlights
    
    async def extract_highlights_async(self, input_video):
        video_path = Path(input_video)
        if not video_path.exists():
            print(f"Video file does not exist: {video_path}")
            return []
        print(f"Starting highlight extraction for {video_path}")
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(2)
        try:
            video_id = self.get_video_id_from_path(video_path)
            async with self._semaphore:
                return await asyncio.to_thread(
                    self._extract_clips_using_auto_editor,
                    str(video_path),
                    video_id
                )
        except Exception as e:
            print(f"Error in async highlight extraction: {e}")
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
        tasks = []
        for path in video_paths:
            tasks.append(asyncio.create_task(self.extract_highlights_async(path)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_highlights = []
        for result in results:
            if isinstance(result, list):
                all_highlights.extend(result)
            else:
                print(f"Error in batch processing: {result}")
        return all_highlights

if __name__ == "__main__":
    import asyncio
    async def main():
        extractor = HighlightExtractor("output")
        input_video = "input.mp4"
        if os.path.exists(input_video):
            highlight_clips = await extractor.extract_highlights_async(input_video)
            print(f"Extracted {len(highlight_clips)} highlight clip(s)")
    asyncio.run(main())