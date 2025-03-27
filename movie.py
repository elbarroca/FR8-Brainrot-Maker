import os
import json
import ffmpeg
from faster_whisper import WhisperModel
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
from PIL import ImageFont
import requests

# Google Fonts to download and use
GOOGLE_FONTS = {
    "Roboto": "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxKKTU1Kg.woff2",
    "Open Sans": "https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4gaVI.woff2",
    "Montserrat": "https://fonts.gstatic.com/s/montserrat/v25/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXo.woff2",
    "Poppins": "https://fonts.gstatic.com/s/poppins/v20/pxiEyp8kv8JHgFVrJJfecg.woff2",
    "Lato": "https://fonts.gstatic.com/s/lato/v24/S6uyw4BMUTPHjx4wXg.woff2",
    "Oswald": "https://fonts.gstatic.com/s/oswald/v49/TK3_WkUHHAIjg75cFRf3bXL8LICs1_FvsUhiZQ.woff2",
    "Roboto Condensed": "https://fonts.gstatic.com/s/robotocondensed/v25/ieVl2ZhZI2eCN5jzbjEETS9weq8-19K7DQ.woff2"
}

# Register fonts at the module level to make them available
def register_fonts():
    """Register custom fonts to make them available to Pillow/ImageFont"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(base_dir, "fonts")
    
    if not os.path.exists(fonts_dir):
        print(f"Creating fonts directory at {fonts_dir}")
        os.makedirs(fonts_dir, exist_ok=True)
    
    # Font paths dictionary to store all available fonts
    font_paths = {}
    
    # First, ensure we have the Poppins fonts from the autocaption repo
    poppins_bold_url = 'https://github.com/fictions-ai/autocaption/raw/main/Poppins/Poppins-Bold.ttf'
    poppins_regular_url = 'https://github.com/fictions-ai/autocaption/raw/main/Poppins/Poppins-Regular.ttf'
    
    poppins_bold_path = os.path.join(fonts_dir, "Poppins-Bold.ttf")
    poppins_regular_path = os.path.join(fonts_dir, "Poppins-Regular.ttf")
    
    # Download Poppins fonts if they don't exist
    if not os.path.exists(poppins_bold_path) or os.path.getsize(poppins_bold_path) < 1000:
        try:
            print(f"Downloading Poppins Bold font...")
            response = requests.get(poppins_bold_url)
            with open(poppins_bold_path, 'wb') as f:
                f.write(response.content)
            font_paths['bold'] = poppins_bold_path
        except Exception as e:
            print(f"Error downloading Poppins Bold: {e}")
    else:
        font_paths['bold'] = poppins_bold_path
        
    if not os.path.exists(poppins_regular_path) or os.path.getsize(poppins_regular_path) < 1000:
        try:
            print(f"Downloading Poppins Regular font...")
            response = requests.get(poppins_regular_url)
            with open(poppins_regular_path, 'wb') as f:
                f.write(response.content)
            font_paths['regular'] = poppins_regular_path
        except Exception as e:
            print(f"Error downloading Poppins Regular: {e}")
    else:
        font_paths['regular'] = poppins_regular_path
    
    # Instead of relying on system fonts, let's just use Google Fonts as woff2 files
    # Most Google Fonts we can download directly
    for font_name, font_url in GOOGLE_FONTS.items():
        safe_name = font_name.replace(" ", "")
        font_path = os.path.join(fonts_dir, f"{safe_name}.ttf")
        
        # Skip if TTF already exists
        if os.path.exists(font_path) and os.path.getsize(font_path) > 1000:
            font_paths[safe_name.lower()] = font_path
            continue
            
        try:
            print(f"Downloading {font_name} font...")
            response = requests.get(font_url)
            # Just save it as ttf directly instead of woff2
            with open(font_path, 'wb') as f:
                f.write(response.content)
            font_paths[safe_name.lower()] = font_path
        except Exception as e:
            print(f"Error downloading {font_name} font: {e}")
    
    # No need to copy system fonts, which can cause permission issues
    # Just use what we have downloaded
    
    # Register all fonts with PIL
    for font_name, font_path in font_paths.items():
        try:
            if os.path.exists(font_path):
                ImageFont.truetype(font_path, size=20)
                print(f"Successfully registered font: {font_name}")
            else:
                print(f"Warning: Font file not found at {font_path}")
        except Exception as e:
            print(f"Error registering font {font_name}: {e}")
    
    # If no fonts were registered, create a fallback font path dictionary
    if not font_paths:
        print("No fonts were registered, using fallback font path strings")
        font_paths = {
            'arial': 'Arial',
            'helvetica': 'Helvetica',
            'verdana': 'Verdana',
            'timesnewroman': 'Times New Roman',
            'georgia': 'Georgia'
        }
    
    return font_paths

# Register fonts at module import time
FONTS = register_fonts()

def create_audio(videofilename):
    """Extract audio from video file"""
    try:
        # Create audio filename from video filename - handle all possible extensions
        base_name = os.path.splitext(videofilename)[0]
        audiofilename = f"{base_name}.mp3"

        # Check if source video exists and is readable
        if not os.path.exists(videofilename):
            print(f"Video file not found: {videofilename}")
            return None
            
        # Skip extraction if audio file already exists
        if os.path.exists(audiofilename) and os.path.getsize(audiofilename) > 0:
            print(f"Using existing audio file: {audiofilename}")
            return audiofilename

        try:
            # Try the ffmpeg-python library first
            input_stream = ffmpeg.input(videofilename)
            audio = input_stream.audio
            output_stream = ffmpeg.output(audio, audiofilename)
            output_stream = ffmpeg.overwrite_output(output_stream)
            ffmpeg.run(output_stream, quiet=True)
        except Exception as e:
            print(f"Error with ffmpeg-python: {e}")
            
            # Fallback to using subprocess directly
            print("Trying fallback audio extraction method...")
            import subprocess
            subprocess.run([
                "ffmpeg", "-y",
                "-i", videofilename,
                "-q:a", "0", "-map", "a",
                audiofilename
            ], check=True)
        
        # Verify the extraction worked
        if os.path.exists(audiofilename) and os.path.getsize(audiofilename) > 0:
            print(f"Successfully extracted audio to: {audiofilename}")
            return audiofilename
        else:
            print(f"Failed to extract audio (empty file): {audiofilename}")
            return None
    
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None

def transcribe_audio(whisper_model, audiofilename):
    """Transcribe audio file using Whisper model"""
    try:
        # Check if audio file exists
        if not os.path.exists(audiofilename):
            print(f"Audio file not found: {audiofilename}")
            return [{'word': 'AUDIO FILE NOT FOUND', 'start': 0.0, 'end': 2.0}]
            
        # Get audio duration to validate
        try:
            import subprocess
            result = subprocess.run([
                "ffprobe", "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                audiofilename
            ], capture_output=True, text=True, check=True)
            
            duration = float(result.stdout.strip())
            if duration < 0.1:
                print(f"Audio file too short ({duration}s): {audiofilename}")
                return [{'word': 'TOO SHORT', 'start': 0.0, 'end': 1.0}]
                
        except Exception as duration_error:
            print(f"Could not check audio duration: {duration_error}")
            # Continue anyway
        
        # Perform transcription with timeout handling
        segments, info = whisper_model.transcribe(audiofilename, word_timestamps=True)

        # The transcription will actually run here
        try:
            segments = list(segments)
        except Exception as list_error:
            print(f"Error listing segments: {list_error}")
            return [{'word': 'TRANSCRIPTION ERROR', 'start': 0.0, 'end': 2.0}]

        wordlevel_info = []

        for segment in segments:
            try:
                for word in segment.words:
                    wordlevel_info.append({
                        'word': word.word.upper(), 
                        'start': word.start, 
                        'end': word.end
                    })
            except Exception as word_error:
                print(f"Error processing words in segment: {word_error}")
                continue

        # If no words were transcribed, add a placeholder
        if not wordlevel_info:
            wordlevel_info = [{'word': 'NO SPEECH DETECTED', 'start': 0.0, 'end': 2.0}]
        
        return wordlevel_info
        
    except Exception as e:
        print(f"Transcription error: {e}")
        return [{'word': 'TRANSCRIPTION FAILED', 'start': 0.0, 'end': 2.0}]

def split_text_into_lines(data, v_type, MaxChars):
    """Split transcribed words into subtitle lines"""
    MaxDuration = 2.5

    # Split if nothing is spoken (gap) for these many seconds
    MaxGap = 1.5

    subtitles = []
    line = []
    line_duration = 0
    line_chars = 0

    for idx, word_data in enumerate(data):
        word = word_data["word"]
        start = word_data["start"]
        end = word_data["end"]

        line.append(word_data)
        line_duration += end - start

        temp = " ".join(item["word"] for item in line)

        # Check if adding a new word exceeds the maximum character count or duration
        new_line_chars = len(temp)

        duration_exceeded = line_duration > MaxDuration
        chars_exceeded = new_line_chars > MaxChars
        if idx > 0:
            gap = word_data['start'] - data[idx - 1]['end']
            # print (word,start,end,gap)
            maxgap_exceeded = gap > MaxGap
        else:
            maxgap_exceeded = False

        if duration_exceeded or chars_exceeded or maxgap_exceeded:
            if line:
                subtitle_line = {
                    "word": " ".join(item["word"] for item in line),
                    "start": line[0]["start"],
                    "end": line[-1]["end"],
                    "textcontents": line
                }
                subtitles.append(subtitle_line)
                line = []
                line_duration = 0
                line_chars = 0

    if line:
        subtitle_line = {
            "word": " ".join(item["word"] for item in line),
            "start": line[0]["start"],
            "end": line[-1]["end"],
            "textcontents": line
        }
        subtitles.append(subtitle_line)

    return subtitles

def set_clip_position(clip, position, relative=False):
    """Helper function to set position compatibly with different MoviePy versions"""
    try:
        return clip.set_position(position, relative=relative)
    except (AttributeError, TypeError):
        try:
            return clip.with_position(position, relative=relative)
        except (AttributeError, TypeError):
            try:
                # Try without relative parameter (older versions)
                if relative:
                    print("Warning: Relative positioning not supported, using absolute")
                return clip.set_position(position)
            except AttributeError:
                try:
                    return clip.with_position(position)
                except AttributeError:
                    # Last resort - return unmodified clip
                    print(f"Warning: Could not set position on clip, returning unmodified")
                    return clip

def create_caption(textJSON, framesize, v_type, highlight_color, fontsize, color, font="Arial", stroke_color='black', stroke_width=2.6):
    """Create a single text clip for each subtitle line with auto-wrapping"""
    # Get frame dimensions
    frame_width, frame_height = framesize
    
    # Calculate duration
    start_time = textJSON['start']
    end_time = textJSON['end']
    duration = end_time - start_time
    
    # Use smaller font size (4% of video height)
    font_size = int(frame_height * 0.04)
    
    # Set max width for text wrapping (80% of frame width)
    max_text_width = int(frame_width * 0.8)
    
    # Get bold font path
    bold_font_path = None
    if FONTS and 'bold' in FONTS and os.path.exists(FONTS['bold']):
        bold_font_path = FONTS['bold']
    else:
        bold_font_path = font  # Use the font parameter as fallback
    
    # Set appropriate stroke width based on font size
    stroke_width = max(1.5, fontsize / 25)
    
    # Create the complete subtitle text
    full_text = " ".join([word['word'] for word in textJSON['textcontents']])
    
    # Add this check inside create_caption
    if color and not color.startswith('#') and not color in ['white', 'black', 'red', 'blue', 'green', 'yellow']:
        color = f"#{color}"
    
    # Create a single text clip with auto-wrapping
    try:
        text_clip = TextClip(
            text=full_text,
            font=bold_font_path,
            font_size=font_size,
            color=color,
            stroke_color=stroke_color,
            stroke_width=int(stroke_width),
            method="caption",
            size=(max_text_width, None)
        )
        
        # Set timing
        text_clip = text_clip.with_start(start_time).with_duration(duration)
        
        # Add fade effects
        try:
            from moviepy.video.fx import fadeout, fadein
            fade_duration = min(0.15, duration / 8)
            text_clip = text_clip.fx(fadein, fade_duration)
            text_clip = text_clip.fx(fadeout, fade_duration)
        except ImportError:
            pass
        
        return [text_clip], [{"word": full_text, "start": start_time, "end": end_time, "duration": duration}]
        
    except Exception as e:
        print(f"Error creating caption: {e}")
        return [], []

def get_final_cliped_video(videofilename, linelevel_subtitles, v_type, subs_position, highlight_color, fontsize, opacity, color, output_dir):
    """Apply subtitles to video with highlighting effect"""
    try:
        # IMPORTANT: Explicitly override any position parameter to ensure only center
        # This prevents any function calls with "bottom" position from creating subtitles
        subs_position = "center"
        
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'output.mp4')
        
        # Validate video file
        if not os.path.exists(videofilename):
            print(f"Video file doesn't exist: {videofilename}")
            return videofilename
            
        # Validate subtitle data
        if not linelevel_subtitles or not isinstance(linelevel_subtitles, list):
            print("Invalid subtitle data, returning original video")
            return videofilename
            
        try:
            # Try to load the video file
            input_video = VideoFileClip(videofilename)
        except Exception as e:
            print(f"Error loading video file: {e}")
            return videofilename
                
        frame_size = input_video.size
        all_linelevel_splits = []

        for line in linelevel_subtitles:
            try:
                # Verify line has required fields
                if not all(key in line for key in ['word', 'start', 'end']):
                    continue
                    
                # Create caption for this line - Use the color parameter passed from the style
                out_clips, positions = create_caption(line, frame_size, v_type, None, fontsize, color)
                
                # Skip if no clips or positions were created
                if not out_clips or not positions:
                    continue
                
                # Create the text overlay without background
                clip_to_overlay = CompositeVideoClip(out_clips)

                # Position in center only
                video_width, video_height = input_video.size
                overlay_width, overlay_height = clip_to_overlay.size
                
                # Calculate center coordinates
                x_center = (video_width - overlay_width) / 2
                y_center = (video_height - overlay_height) / 2
                
                # Center positioning only
                clip_to_overlay = set_clip_position(clip_to_overlay, (x_center, y_center))
                all_linelevel_splits.append(clip_to_overlay)
                
            except Exception as line_error:
                print(f"Error processing subtitle line: {line_error}")
                continue

        # If we couldn't create any subtitle overlays, return original video
        if not all_linelevel_splits:
            return videofilename

        # Create final composite video with ONLY center white subtitles
        try:
            final_video = CompositeVideoClip([input_video] + all_linelevel_splits)
            
            # Set the audio of the final video
            if input_video.audio is not None:
                try:
                    # First try set_audio
                    final_video = final_video.set_audio(input_video.audio)
                except (AttributeError, TypeError):
                    try:
                        # Then try set_audio_all
                        final_video = final_video.set_audio_all(input_video.audio)
                    except (AttributeError, TypeError):
                        try:
                            # Try audio_fadein
                            final_video = final_video.audio_fadein(0)
                        except (AttributeError, TypeError):
                            # Last resort - create a new CompositeVideoClip
                            print("Using alternative method for audio attachment")
                            try:
                                final_video = CompositeVideoClip([final_video])
                                final_video.audio = input_video.audio
                            except Exception as audio_error:
                                print(f"Could not attach audio: {audio_error}")
            
            # Write the final video file
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                threads=2,
                logger=None
            )
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                return videofilename
                
        except Exception as render_error:
            print(f"Error rendering final video: {render_error}")
            return videofilename
            
    except Exception as e:
        print(f"Global error in get_final_cliped_video: {e}")
        return videofilename

def format_srt_time(seconds):
    """Format time in SRT format (HH:MM:SS,mmm)"""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    secs = seconds % 60
    milliseconds = int((secs - int(secs)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{milliseconds:03d}"

def add_subtitle(videofilename, audiofilename, v_type, subs_position, highlight_color, fontsize, opacity, MaxChars, color, wordlevel_info, output_dir):
    """Complete process to add subtitles to a video"""
    try:
        print("video type is: " + v_type)
        print("Video and Audio files are: ", videofilename, audiofilename)
        
        # Validate input files
        if not os.path.exists(videofilename):
            print(f"Video file not found: {videofilename}")
            return videofilename, []
            
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Ensure we have valid wordlevel info
        if not wordlevel_info or not isinstance(wordlevel_info, list):
            print("Empty or invalid word-level info, creating placeholder")
            # Create dummy wordlevel info as fallback
            duration = 5.0
            try:
                # Try to get actual video duration
                import subprocess
                result = subprocess.run([
                    "ffprobe", "-v", "error", 
                    "-show_entries", "format=duration", 
                    "-of", "default=noprint_wrappers=1:nokey=1", 
                    videofilename
                ], capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())
            except Exception as e:
                print(f"Could not get video duration: {e}")
                
            wordlevel_info = [{'word': 'NO SUBTITLES AVAILABLE', 'start': 0.0, 'end': min(duration, 5.0)}]
        
        print("word_level: ", wordlevel_info)
        
        # Generate line-level subtitles - use the approach from the example
        try:
            linelevel_subtitles = split_text_into_lines(wordlevel_info, v_type, MaxChars)
            print("line_level_subtitles:", linelevel_subtitles)
            
            if not linelevel_subtitles:
                print("No line-level subtitles were generated, creating fallback")
                # Create a fallback subtitle if no lines were created
                linelevel_subtitles = [{
                    "word": wordlevel_info[0]["word"] if wordlevel_info else "NO SUBTITLES",
                    "start": wordlevel_info[0]["start"] if wordlevel_info else 0.0,
                    "end": wordlevel_info[0]["end"] if wordlevel_info else 5.0,
                    "textcontents": wordlevel_info if wordlevel_info else [{'word': 'NO SUBTITLES', 'start': 0.0, 'end': 5.0}]
                }]
            
            for line in linelevel_subtitles:
                json_str = json.dumps(line, indent=4)
                print("whole json: ", json_str)
                
            # Apply subtitles to the video - simplified as in the example
            outputfile = get_final_cliped_video(videofilename, linelevel_subtitles, v_type, subs_position, highlight_color, fontsize, opacity, color, output_dir)
            return outputfile, linelevel_subtitles
            
        except Exception as e:
            print(f"Error processing subtitles: {e}")
            # Create a fallback subtitle if processing failed
            linelevel_subtitles = [{
                "word": "SUBTITLE PROCESSING ERROR",
                "start": 0.0,
                "end": 5.0,
                "textcontents": [{'word': 'SUBTITLE PROCESSING ERROR', 'start': 0.0, 'end': 5.0}]
            }]
            
            # Try to apply even the error subtitle
            try:
                outputfile = get_final_cliped_video(videofilename, linelevel_subtitles, v_type, subs_position, highlight_color, fontsize, opacity, color, output_dir)
                return outputfile, linelevel_subtitles
            except Exception as e2:
                print(f"Error applying fallback subtitles: {e2}")
                return videofilename, linelevel_subtitles
            
    except Exception as e:
        print(f"Global error in add_subtitle: {e}")
        # Return original video as fallback
        return videofilename, []

def load_whisper_model(model_size="base"):
    """Load and initialize the Whisper model"""
    print('Loading the Whisper Model...')
    try:
        # First try with CUDA
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
        print("Model loaded with CUDA support")
    except (RuntimeError, ValueError) as e:
        # Fall back to CPU if CUDA is not available
        print(f"CUDA not available: {e}")
        print("Loading model on CPU instead...")
        model = WhisperModel(model_size, device="cpu", compute_type="float32")
        print("Model loaded with CPU support")
    
    print("Model loaded successfully!")
    return model

def test_subtitle_pipeline(input_video_path, output_dir="output"):
    """Test the complete subtitling pipeline with a sample video"""
    print(f"Testing subtitle pipeline with video: {input_video_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Extract audio from video
    audio_path = create_audio(input_video_path)
    if not audio_path:
        print("Audio extraction failed")
        return None
    
    # 2. Load Whisper model
    model = load_whisper_model("base")
    
    # 3. Transcribe audio
    word_level_info = transcribe_audio(model, audio_path)
    
    # 4. Add subtitles to video - CHANGED to match test_movie.py settings
    v_type = "9x16"  # Changed from "highlights" to "9x16"
    subs_position = "center"  # Changed from "bottom75" to "center"
    highlight_color = None  # Changed from "yellow" to None
    fontsize = 7.0  # Changed from 5 to 7.0
    opacity = 0.0  # Changed from 0.8 to 0.0
    max_chars = 12  # Changed from 50 to 12
    text_color = "white"  # Changed from "yellow" to "white"
    
    # 5. Process and add subtitles
    output_path, _ = add_subtitle(
        input_video_path, 
        audio_path, 
        v_type, 
        subs_position, 
        highlight_color, 
        fontsize, 
        opacity, 
        max_chars, 
        text_color, 
        word_level_info, 
        output_dir
    )
    
    print(f"Subtitling complete! Output saved to: {output_path}")
    return output_path

# Example usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        test_subtitle_pipeline(video_path)
    else:
        print("Usage: python movie.py <video_path>") 