import streamlit as st
import os
import asyncio
import tempfile
from pathlib import Path
import time
import streamlit.components.v1 as components
import zipfile

# Import from our modules
from movie import load_whisper_model
from brainrot_pipeline import process_video

# Pong Game implementation using HTML5/JavaScript for Streamlit
def show_pong_game():
    """Display a simple Pong game in Streamlit while processing"""
    pong_game_html = """
    <div style="width:100%; max-width:500px; margin:0 auto; background:#111; border-radius:10px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.2);">
        <h3 style="text-align:center; color:white; padding:15px; margin:0; background:linear-gradient(90deg, #FF5F6D 0%, #FFC371 100%);">🏓 Pong Game</h3>
        <p style="text-align:center; color:#ccc; margin:0; padding:10px;">Play while your video is being processed!</p>
        <div style="padding:0 15px 15px;">
            <canvas id="pongCanvas" width="470" height="300" style="background:#222; border-radius:8px; box-shadow:inset 0 0 10px rgba(0,0,0,0.5);"></canvas>
        </div>
        <div style="padding:0 15px 15px; text-align:center; color:white;">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <div style="padding:5px 10px; background:#333; border-radius:5px;">
                    Player: <span id="leftScore">0</span>
                </div>
                <div style="padding:5px 10px; background:#333; border-radius:5px;">
                    CPU: <span id="rightScore">0</span>
                </div>
            </div>
            <div style="background:#222; padding:10px; border-radius:5px; margin-bottom:10px;">
                Controls: <span style="color:#FF5F6D">W/S</span> or <span style="color:#FF5F6D">↑/↓</span> to move paddle
            </div>
            <p style="font-size:12px; color:#aaa; margin-top:15px;">Game automatically pauses when you click outside</p>
        </div>
    </div>
    <script>
        const canvas = document.getElementById('pongCanvas');
        const ctx = canvas.getContext('2d');
        const leftScoreDisplay = document.getElementById('leftScore');
        const rightScoreDisplay = document.getElementById('rightScore');
        
        const paddleWidth = 10;
        const paddleHeight = 70;
        const ballRadius = 8;
        let leftPaddleY = canvas.height / 2 - paddleHeight / 2;
        let rightPaddleY = canvas.height / 2 - paddleHeight / 2;
        let ballX = canvas.width / 2;
        let ballY = canvas.height / 2;
        let ballSpeedX = 4;
        let ballSpeedY = 4;
        let leftScore = 0;
        let rightScore = 0;
        let keysPressed = {};
        let gamePaused = false;
        let particles = [];
        let aiDifficulty = 0.8; 
        let aiReactionSpeed = 3; // Lower = faster
        
        document.addEventListener('keydown', function(e) {
            keysPressed[e.key] = true;
            if (['w', 's', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
                e.preventDefault();
            }
        });
        
        document.addEventListener('keyup', function(e) {
            keysPressed[e.key] = false;
        });
        
        canvas.addEventListener('focus', function() {
            gamePaused = false;
        });
        
        canvas.addEventListener('blur', function() {
            gamePaused = true;
        });
        
        canvas.addEventListener('click', function() {
            canvas.focus();
            gamePaused = false;
        });
        
        canvas.setAttribute('tabindex', '0');
        
        class Particle {
            constructor(x, y, color) {
                this.x = x;
                this.y = y;
                this.size = Math.random() * 3 + 2;
                this.speedX = Math.random() * 4 - 2;
                this.speedY = Math.random() * 4 - 2;
                this.color = color;
                this.life = 1.0; // Full life
                this.fadeSpeed = Math.random() * 0.05 + 0.02;
            }
            
            update() {
                this.x += this.speedX;
                this.y += this.speedY;
                this.life -= this.fadeSpeed;
                this.size = Math.max(0, this.size - 0.1);
            }
            
            draw() {
                ctx.globalAlpha = this.life;
                ctx.fillStyle = this.color;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalAlpha = 1;
            }
        }
        
        function createParticles(x, y, count, color) {
            for (let i = 0; i < count; i++) {
                particles.push(new Particle(x, y, color));
            }
        }
        
        function moveAI() {
            if (ballSpeedX > 0) { // Only move if ball is coming toward AI
                const distanceToRightSide = canvas.width - ballRadius - ballX;
                const timeToReachRightSide = distanceToRightSide / ballSpeedX;
                const predictedY = ballY + (ballSpeedY * timeToReachRightSide);
                
                const targetY = predictedY + (Math.random() * 20 - 10) * (1 - aiDifficulty);
                
                const paddleCenter = rightPaddleY + paddleHeight / 2;
                if (paddleCenter < targetY - 10) {
                    rightPaddleY += aiReactionSpeed * aiDifficulty;
                } else if (paddleCenter > targetY + 10) {
                    rightPaddleY -= aiReactionSpeed * aiDifficulty;
                }
                
                rightPaddleY = Math.max(0, Math.min(canvas.height - paddleHeight, rightPaddleY));
            }
        }
                function gameLoop() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(canvas.width / 2, 0);
            ctx.lineTo(canvas.width / 2, canvas.height);
            ctx.stroke();
            ctx.setLineDash([]);
            
            ctx.beginPath();
            ctx.arc(canvas.width / 2, canvas.height / 2, 30, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.stroke();
            
            const leftPaddleGradient = ctx.createLinearGradient(0, leftPaddleY, paddleWidth, leftPaddleY + paddleHeight);
            leftPaddleGradient.addColorStop(0, '#FF5F6D');
            leftPaddleGradient.addColorStop(1, '#FF8F9D');
            ctx.fillStyle = leftPaddleGradient;
            ctx.fillRect(10, leftPaddleY, paddleWidth, paddleHeight);
            
            const rightPaddleGradient = ctx.createLinearGradient(canvas.width - paddleWidth - 10, rightPaddleY, canvas.width - 10, rightPaddleY + paddleHeight);
            rightPaddleGradient.addColorStop(0, '#FFC371');
            rightPaddleGradient.addColorStop(1, '#FFD391');
            ctx.fillStyle = rightPaddleGradient;
            ctx.fillRect(canvas.width - paddleWidth - 10, rightPaddleY, paddleWidth, paddleHeight);
            
            const ballGradient = ctx.createRadialGradient(ballX, ballY, 0, ballX, ballY, ballRadius);
            ballGradient.addColorStop(0, '#FFFFFF');
            ballGradient.addColorStop(1, '#FF5F6D');
            ctx.beginPath();
            ctx.arc(ballX, ballY, ballRadius, 0, Math.PI * 2);
            ctx.fillStyle = ballGradient;
            ctx.fill();
            
            ctx.beginPath();
            ctx.arc(ballX + 2, ballY + 2, ballRadius, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
            ctx.fill();
            
            for (let i = particles.length - 1; i >= 0; i--) {
                particles[i].update();
                particles[i].draw();
                
                if (particles[i].life <= 0) {
                    particles.splice(i, 1);
                }
            }
            
            if (gamePaused) {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.font = '24px Arial';
                ctx.fillStyle = 'white';
                ctx.textAlign = 'center';
                ctx.fillText('Click to Play', canvas.width / 2, canvas.height / 2);
                requestAnimationFrame(gameLoop);
                return;
            }
            
            moveAI();
            
            if ((keysPressed['w'] || keysPressed['W'] || keysPressed['ArrowUp']) && leftPaddleY > 0) {
                leftPaddleY -= 6;
            }
            if ((keysPressed['s'] || keysPressed['S'] || keysPressed['ArrowDown']) && leftPaddleY < canvas.height - paddleHeight) {
                leftPaddleY += 6;
            }
            
            ballX += ballSpeedX;
            ballY += ballSpeedY;
            
            if (ballY - ballRadius < 0 || ballY + ballRadius > canvas.height) {
                ballSpeedY = -ballSpeedY;
                createParticles(ballX, ballY < ballRadius ? 0 : canvas.height, 10, '#FFF');
            }
            
            if (
                ballX - ballRadius < 20 && 
                ballY > leftPaddleY && 
                ballY < leftPaddleY + paddleHeight
            ) {
                const hitPosition = (ballY - leftPaddleY) / paddleHeight;
                const angle = (hitPosition - 0.5) * Math.PI / 2; // -PI/4 to PI/4
                
                ballSpeedX = Math.abs(ballSpeedX) * 1.05; // Increase speed slightly
                ballSpeedY = Math.sin(angle) * 6;
                
                aiDifficulty = Math.min(0.95, aiDifficulty + 0.01);
                
                createParticles(ballX, ballY, 15, '#FF5F6D');
            }
            
            if (
                ballX + ballRadius > canvas.width - 20 && 
                ballY > rightPaddleY && 
                ballY < rightPaddleY + paddleHeight
            ) {
                const hitPosition = (ballY - rightPaddleY) / paddleHeight;
                const angle = (hitPosition - 0.5) * Math.PI / 2; // -PI/4 to PI/4
                
                ballSpeedX = -Math.abs(ballSpeedX) * 1.05; // Increase speed slightly
                ballSpeedY = Math.sin(angle) * 6;
                
                createParticles(ballX, ballY, 15, '#FFC371');
            }
            
            if (ballX < 0) {
                rightScore++;
                rightScoreDisplay.textContent = rightScore;
                createParticles(0, ballY, 30, '#FFC371');
                aiDifficulty = Math.max(0.7, aiDifficulty - 0.05); // Decrease difficulty slightly
                resetBall();
            } else if (ballX > canvas.width) {
                leftScore++;
                leftScoreDisplay.textContent = leftScore;
                createParticles(canvas.width, ballY, 30, '#FF5F6D');
                aiDifficulty = Math.min(0.95, aiDifficulty + 0.05); // Increase difficulty slightly
                resetBall();
            }
            
            const maxSpeed = 12;
            if (Math.abs(ballSpeedX) > maxSpeed) {
                ballSpeedX = maxSpeed * Math.sign(ballSpeedX);
            }
            if (Math.abs(ballSpeedY) > maxSpeed) {
                ballSpeedY = maxSpeed * Math.sign(ballSpeedY);
            }
            
            requestAnimationFrame(gameLoop);
        }
        
        function resetBall() {
            ballX = canvas.width / 2;
            ballY = canvas.height / 2;
            
            const angle = (Math.random() - 0.5) * Math.PI / 2;
            const direction = Math.random() > 0.7 ? -1 : 1;
            
            ballSpeedX = direction * 4 * Math.cos(angle);
            ballSpeedY = 4 * Math.sin(angle);
        }
        
        canvas.focus();
        gameLoop();
    </script>
    """
    
    # Display the game in Streamlit
    components.html(pong_game_html, height=450)

# Initialize session state variables
if 'processed_clips' not in st.session_state:
    st.session_state.processed_clips = []
if 'selected_clip_index' not in st.session_state:
    st.session_state.selected_clip_index = 0
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = None
if 'show_games' not in st.session_state:
    st.session_state.show_games = False

# Set page configuration
st.set_page_config(
    page_title="Brainrot Video Automation",
    page_icon="🎬",
    layout="wide"
)

# Add custom CSS for compact clips and games integration
st.markdown("""
<style>
.compact-video {
    margin: 0 auto;
    display: flex;
    justify-content: center;
    width: 100%;
}
.stVideo {
    max-width: 200px !important;
}
.stVideo video {
    max-height: 350px !important;
}
.clip-container {
    background: #f0f2f6;
    border-radius: 10px;
    padding: 10px;
    margin: 10px 0;
    transition: all 0.3s ease;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    height: 100%;
    display: flex;
    flex-direction: column;
}
.clip-container:hover {
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}
.clip-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 15px;
    padding: 20px 0;
}
.processing-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding: 20px;
    background: #f9f9f9;
    border-radius: 10px;
    margin-top: 20px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.progress-section {
    padding: 15px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.games-section {
    padding: 15px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    display: flex;
    justify-content: center;
    align-items: center;
    flex-direction: column;
}
.games-section h3 {
    color: #FF5F6D;
    margin-bottom: 15px;
    text-align: center;
}
.game-canvas {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    background: #222;
}
.processing-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.processing-header h3 {
    margin: 0;
}
.clip-title {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
    text-align: center;
}
.clip-buttons {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
}
.clip-buttons button {
    padding: 3px 8px;
    font-size: 12px;
    border-radius: 4px;
}
.main-header {
    background: linear-gradient(90deg, #FF5F6D 0%, #FFC371 100%);
    padding: 15px;
    border-radius: 10px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.batch-download {
    background: #f0f2f6;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 20px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    text-align: center;
}
.highlight-counter {
    font-weight: bold;
    margin-top: 10px;
    color: #FF5F6D;
}
.status-text {
    font-style: italic;
    margin-bottom: 5px;
}
</style>
""", unsafe_allow_html=True)

# Main header with attractive gradient
st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title('🎬 Brainrot Video Automation')
st.write("Transform YouTube videos into viral mobile-ready Brainrot clips")
st.markdown('</div>', unsafe_allow_html=True)

# Initialize model only once
@st.cache_resource
def get_whisper_model():
    st.info('Loading Whisper Model...')
    model = load_whisper_model("small")
    st.success("Model loaded successfully!")
    return model

# Create temp directory for file storage
output_dir = Path(tempfile.gettempdir()) / "brainrot_output"
output_dir.mkdir(exist_ok=True)

# Initialize Whisper model
if 'whisper_model' not in st.session_state:
    with st.spinner("Initializing AI components..."):
        model = get_whisper_model()
        st.session_state.whisper_model = model

# Main interface
st.header("Step 1: Enter YouTube Link")
youtube_url = st.text_input("Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# Find available background videos
def find_background_videos():
    """Find all available background videos in assets folder"""
    background_videos = []
    
    # Check common locations for background videos
    asset_paths = [
        Path("assets"),
        Path("./assets"),
        Path("../assets"),
        Path("/Users/barroca888/FR8/Brainrot Automacion/assets"),
        Path.home() / "FR8/Brainrot Automacion/assets"
    ]
    
    for base_path in asset_paths:
        if base_path.exists():
            for video_file in base_path.glob("*.mp4"):
                background_videos.append({
                    "name": video_file.stem,
                    "path": str(video_file)
                })
    
    return background_videos

# Get available background videos
background_videos = find_background_videos()

# Background video selection
st.subheader("Background Video")
if background_videos:
    bg_options = ["Automatic"] + [video["name"] for video in background_videos]
    selected_bg = st.selectbox("Select background video", bg_options)
    
    if selected_bg == "Automatic":
        st.info("The app will automatically select a background video")
        bg_video_path = None
    else:
        for video in background_videos:
            if video["name"] == selected_bg:
                bg_video_path = video["path"]
                st.success(f"✅ Using {selected_bg} as background video")
                break
else:
    st.error("⚠️ No background videos found! Please add MP4 files to the assets folder.")
    bg_video_path = None

# Process button
process_button = st.button("Process YouTube Video", type="primary", disabled=not youtube_url)

if youtube_url and process_button:
    # Clear previous results
    st.session_state.processed_clips = []
    st.session_state.processing_status = "processing"
    st.session_state.show_games = True
    
    # Create a container for the processing UI
    processing_container = st.container()
    
    with processing_container:
        st.markdown('<div class="processing-container">', unsafe_allow_html=True)
        
        # Processing header
        st.markdown('<div class="processing-header"><h3>🔄 Processing Your Video</h3></div>', unsafe_allow_html=True)
        
        # Progress section
        st.markdown('<div class="progress-section">', unsafe_allow_html=True)
        st.subheader("Progress")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.markdown('<div class="status-text">Initializing...</div>', unsafe_allow_html=True)
        highlight_counter = st.empty()
        highlight_counter.markdown('<div class="highlight-counter">Getting ready...</div>', unsafe_allow_html=True)
        progress_text.text("Downloading YouTube video...")
        progress_bar.progress(10)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Games section below processing
        if st.session_state.show_games:
            st.markdown('<div class="games-section">', unsafe_allow_html=True)
            
            # Add auto-refresh for games
            st.markdown("""
            <script>
            // Auto-refresh the games section every 2 seconds during processing
            function refreshGames() {
                if (window.frameElement) {
                    window.frameElement.contentWindow.location.reload();
                }
            }
            setInterval(refreshGames, 2000);
            </script>
            """, unsafe_allow_html=True)
            
            st.subheader("🎮 Entertainment While You Wait")
            st.write("Play a game of Pong while your video is being processed!")
            show_pong_game()
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    try:
        run_output_dir = str(output_dir / f"run_{int(time.time())}")
        os.makedirs(run_output_dir, exist_ok=True)
        
        async def process_with_progress_updates():
            async def update_progress():
                steps = ["Downloading", "Extracting highlights", "Formatting videos", "Transcribing", 
                         "Preparing background", "Adding subtitles", "Creating final videos", "Optimizing"]
                progress_values = [20, 30, 40, 60, 70, 80, 90, 95]
                
                for i, (step, value) in enumerate(zip(steps, progress_values)):
                    progress_text.text(f"{step}...")
                    progress_bar.progress(value)
                    await asyncio.sleep(2)
            
            progress_task = asyncio.create_task(update_progress())
            
            try:
                # Create a queue for tracking highlight processing
                progress_queue = asyncio.Queue()
                
                # Track highlights processing
                async def track_highlights_progress():
                    total_highlights = 0
                    completed_highlights = 0
                    
                    while True:
                        msg = await progress_queue.get()
                        
                        if msg["type"] == "total":
                            total_highlights = msg["count"]
                            status_text.markdown(f'<div class="status-text">Processing {total_highlights} highlights...</div>', unsafe_allow_html=True)
                        elif msg["type"] == "step":
                            current_step = msg["step"]
                            current_highlight = msg["highlight"]
                            status_text.markdown(f'<div class="status-text">Step {current_step}: {msg["description"]} (Highlight {current_highlight})</div>', unsafe_allow_html=True)
                        elif msg["type"] == "completed":
                            completed_highlights += 1
                            percentage = int((completed_highlights / total_highlights) * 100) if total_highlights > 0 else 0
                            highlight_counter.markdown(f'<div class="highlight-counter">Completed: {completed_highlights}/{total_highlights} highlights ({percentage}%)</div>', unsafe_allow_html=True)
                            # Update progress bar based on completed highlights
                            overall_progress = min(95, 40 + (completed_highlights / total_highlights) * 55)
                            progress_bar.progress(int(overall_progress))
                        
                        # Check if we're done
                        if msg.get("done", False) or (total_highlights > 0 and completed_highlights >= total_highlights):
                            break
                
                tracking_task = asyncio.create_task(track_highlights_progress())
                
                # Call process_video with progress updates
                result = await process_video(youtube_url, run_output_dir, bg_video_path, progress_queue)
                
                # Signal completion
                await progress_queue.put({"type": "done", "done": True})
                
                # Wait for tracking to finish
                await tracking_task
                progress_task.cancel()
                return result
            except Exception as e:
                progress_task.cancel()
                raise e
        
        final_clips = asyncio.run(process_with_progress_updates())
        
        if final_clips and len(final_clips) > 0:
            progress_text.text("Processing complete!")
            progress_bar.progress(100)
            st.session_state.processed_clips = final_clips
            st.session_state.processing_status = "completed"
            st.session_state.show_games = False
            
            # Add a celebratory message with animation
            st.balloons()
            st.success(f"🎉 Successfully created {len(final_clips)} clips!")
        else:
            st.error("❌ No clips were generated. Please try another video.")
            st.session_state.processing_status = "error"
            st.session_state.show_games = False
            
    except Exception as e:
        st.error(f"Error processing video: {str(e)}")
        st.session_state.processed_clips = []
        st.session_state.processing_status = "error"
        st.session_state.show_games = False

# Display processed clips in a grid layout
if st.session_state.processed_clips:
    st.header("Step 2: Preview Your Clips")
    
    # Add a short introduction to the clips
    st.write("Here are your processed clips ready for download and sharing:")
    
    # Add Download All button at the top
    if len(st.session_state.processed_clips) > 1:
        st.markdown('<div class="batch-download">', unsafe_allow_html=True)
        st.subheader("Batch Download")
        st.write(f"Download all {len(st.session_state.processed_clips)} clips as a single ZIP file.")
        
        if st.button("📦 Download All Clips as ZIP", type="primary"):
            # Create a temporary ZIP file with all clips
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip_file:
                zip_path = temp_zip_file.name
                
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for i, clip_path in enumerate(st.session_state.processed_clips):
                    if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                        # Add the file to the ZIP with a numbered name
                        zipf.write(clip_path, f"brainrot_clip_{i+1}.mp4")
            
            # Provide the ZIP file for download
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download ZIP File",
                    data=f.read(),
                    file_name=f"brainrot_clips_{len(st.session_state.processed_clips)}.zip",
                    mime="application/zip"
                )
            
            # Clean up the temporary ZIP file
            try:
                os.unlink(zip_path)
            except:
                pass
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display clips in a 4-column grid
    col_count = 4  # Number of columns in the grid
    clips_count = len(st.session_state.processed_clips)
    rows = (clips_count + col_count - 1) // col_count  # Ceiling division to get number of rows
    
    for row in range(rows):
        # Create a row with col_count columns
        cols = st.columns(col_count)
        
        # Fill each column with a clip
        for col in range(col_count):
            clip_index = row * col_count + col
            
            # Check if we still have clips to display
            if clip_index < clips_count:
                clip_path = st.session_state.processed_clips[clip_index]
                
                with cols[col]:
                    st.markdown(f'<div class="clip-container">', unsafe_allow_html=True)
                    
                    if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                        try:
                            # Display video title
                            st.markdown(f'<div class="clip-title">Clip {clip_index+1}</div>', unsafe_allow_html=True)
                            
                            # Display video in compact format with CSS class
                            st.markdown('<div class="compact-video">', unsafe_allow_html=True)
                            st.video(clip_path)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Display download and share buttons
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                with open(clip_path, "rb") as file:
                                    st.download_button(
                                        label="⬇️ Download",
                                        data=file.read(),
                                        file_name=f"brainrot_clip_{clip_index+1}.mp4",
                                        mime="video/mp4"
                                    )
                            with col2:
                                if st.button("📱 Share", key=f"share_{clip_index}"):
                                    st.info("Copy the downloaded file and upload to TikTok, Instagram, or YouTube Shorts!")
                            
                        except Exception as e:
                            st.error(f"Error displaying clip {clip_index+1}: {str(e)}")
                            try:
                                with open(clip_path, "rb") as file:
                                    st.download_button(
                                        label=f"Download Clip {clip_index+1}",
                                        data=file.read(),
                                        file_name=f"brainrot_clip_{clip_index+1}.mp4",
                                        mime="video/mp4"
                                    )
                            except Exception as download_error:
                                st.error(f"Cannot read clip file: {str(download_error)}")
                    else:
                        st.error(f"Clip {clip_index+1} file is missing or empty.")
                    
                    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.processing_status == "error":
    st.error("Processing failed. Please try again with a different YouTube URL.")
elif st.session_state.processing_status == "processing":
    st.info("Processing your video... please wait.")

# Footer
st.divider()
st.markdown("Made with ❤️ by [Ricardo Barroca](https://rbarroca.com) | [GitHub Repo](https://github.com/ricardo-barroca/brainrot-automation)")
