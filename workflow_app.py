import streamlit as st
import os
import asyncio
import tempfile
from pathlib import Path
import time
import streamlit.components.v1 as components
import zipfile
import random
from datetime import datetime

# Import from our modules
from movie import load_whisper_model
from brainrot_workflow import BrainrotWorkflow
from subtitle_styles import SUBTITLE_STYLES

# Funny loading GIFs to show during processing
LOADING_GIFS = [
    "https://media1.giphy.com/media/3o7bu3XilJ5BOiSGic/giphy.gif",     # Spinning wheel
    "https://media2.giphy.com/media/l3nWhI38IWDofyDrW/giphy.gif",      # Cat typing
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnhhYnNqMTJtZGswbXo3cTYxZWhoYTZrc3NibmxxeG02Zmp5NWY5YSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/tXL4FHPSnVJ0A/giphy.gif",  # Dog on computer
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMDN3b3lvb2VoMmd0MXRxNXJ5OGZ5YTdzdnJva3pydnYwOXVnamRqaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JIX9t2j0ZTN9S/giphy.gif",     # Cat looking at screen
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExem1nOGJqNWpseG40cjZjdWRmYndsbzBvZm9hcndrdWE4czRyM3VueiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ule4vhcY1xMAM/giphy.gif",    # Dog waiting
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWNlbGcwMGpscnpidnQ2OWUxbTExdTZvYnpndm5ycm5kbGRuYnl0dCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7btQ0NH6Kl58CIco/giphy.gif"  # Hamster spinning
]

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

def show_wandering_icon():
    """Show a wandering icon that can be clicked to redirect to a YouTube video"""
    icon_url = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Ftse1.mm.bing.net%2Fth%3Fid%3DOIP.9ZgjBJ-fdWzRA1zbpHisTQHaGm%26pid%3DApi&f=1&ipt=a34397bb8f6caf870a6a40da75a179f67f207dd064c2d2438e8cc9ee6157b828&ipo=images"
    target_url = "https://www.youtube.com/watch?v=UMRqhob3oOE"
    
    # JavaScript for wandering icon that appears after 80 seconds
    wandering_icon_js = f"""
    <script>
    // This script adds a wandering icon that appears after 80 seconds
    setTimeout(function() {{
        // Create the icon element
        var icon = document.createElement('div');
        icon.style.position = 'fixed';
        icon.style.zIndex = '9999';
        icon.style.width = '70px';
        icon.style.height = '70px';
        icon.style.cursor = 'pointer';
        icon.style.borderRadius = '50%';
        icon.style.boxShadow = '0 4px 8px rgba(0,0,0,0.3)';
        icon.style.transition = 'transform 0.3s ease';
        icon.innerHTML = '<img src="{icon_url}" style="width:100%; height:100%; border-radius:50%; object-fit:cover;" />';
        
        // Random starting position within 70% of visible area
        var x = Math.random() * (window.innerWidth * 0.7);
        var y = Math.random() * (window.innerHeight * 0.7);
        
        // Random direction and speed
        var dx = (Math.random() - 0.5) * 3;
        var dy = (Math.random() - 0.5) * 3;
        
        icon.style.left = x + 'px';
        icon.style.top = y + 'px';
        
        // Add hover effect
        icon.onmouseover = function() {{
            this.style.transform = 'scale(1.2)';
        }};
        
        icon.onmouseout = function() {{
            this.style.transform = 'scale(1)';
        }};
        
        // Add click handler to redirect
        icon.onclick = function() {{
            window.open('{target_url}', '_blank');
        }};
        
        // Add to document
        document.body.appendChild(icon);
        
        // Animation function for wandering
        function animate() {{
            // Update position
            x += dx;
            y += dy;
            
            // Bounce off edges
            if (x <= 0 || x >= window.innerWidth - 70) {{
                dx = -dx;
                x = Math.max(0, Math.min(x, window.innerWidth - 70));
            }}
            
            if (y <= 0 || y >= window.innerHeight - 70) {{
                dy = -dy;
                y = Math.max(0, Math.min(y, window.innerHeight - 70));
            }}
            
            // Set new position
            icon.style.left = x + 'px';
            icon.style.top = y + 'px';
            
            // Continue animation
            requestAnimationFrame(animate);
        }}
        
        // Start animation
        animate();
    }}, 80000); // 80 seconds delay
    </script>
    """
    
    # Inject JavaScript into Streamlit
    st.markdown(wandering_icon_js, unsafe_allow_html=True)

# Initialize session state variables
if 'processed_clips' not in st.session_state:
    st.session_state.processed_clips = []
if 'selected_clip_index' not in st.session_state:
    st.session_state.selected_clip_index = 0
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = None
if 'show_games' not in st.session_state:
    st.session_state.show_games = False
if 'whisper_model' not in st.session_state:
    # Load whisper model silently at startup
    try:
        st.session_state.whisper_model = load_whisper_model("small")
    except Exception:
        st.session_state.whisper_model = None

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
.advanced-options {
    background: #f6f6f6;
    border-radius: 10px;
    padding: 15px;
    margin-top: 15px;
    margin-bottom: 20px;
    border-left: 4px solid #FF5F6D;
}
.subtitle-preview {
    background: #000;
    color: var(--subtitle-color);
    padding: 8px 16px;
    border-radius: 5px;
    display: inline-block;
    margin: 10px 0;
    text-align: center;
    font-weight: bold;
    text-shadow: var(--subtitle-stroke);
}
.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: #f9f9f9;
    border-radius: 10px;
    margin: 20px 0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.loading-step {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 5px 0;
    padding: 8px;
    border-radius: 5px;
    width: 100%;
}
.loading-step.active {
    background: rgba(255, 95, 109, 0.1);
    border-left: 3px solid #FF5F6D;
}
.loading-step.completed {
    color: #4CAF50;
}
.loading-spinner {
    margin-right: 10px;
}
</style>
""", unsafe_allow_html=True)

# Main header with attractive gradient
st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title('🎬 Brainrot Video Automation')
st.write("Transform YouTube videos into viral mobile-ready Brainrot clips")
st.markdown('</div>', unsafe_allow_html=True)

# Create temp directory for file storage
output_dir = Path(tempfile.gettempdir()) / "brainrot_output"
output_dir.mkdir(exist_ok=True)

# Main interface
st.header("Step 1: Enter YouTube Link")
youtube_url = st.text_input("Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# Add processing time disclaimer
st.markdown("""
<div style="background-color:#fff3cd; color:#856404; padding:12px 15px; border-radius:5px; border-left:4px solid #ffeeba; margin:10px 0; font-size:14px;">
    <strong>⏱️ Processing Time:</strong> On average, it takes approximately 1 minute and 43 seconds to produce a single clip. 
    Please avoid inputting lengthy videos (over 8 minutes) as processing time increases with video duration. It works, we promise!
</div>
""", unsafe_allow_html=True)

# Advanced options toggle
show_advanced = st.checkbox("Show Advanced Options")

if show_advanced:
    st.markdown('<div class="advanced-options">', unsafe_allow_html=True)
    st.subheader("Advanced Configuration")
    
    # Create columns for better organization
    col1, col2 = st.columns(2)
    
    with col1:
        # Highlight extraction parameters
        st.subheader("Highlight Settings")
        min_clip_duration = st.slider("Minimum Clip Duration (seconds)", 5, 30, 10)
        max_clip_duration = st.slider("Maximum Clip Duration (seconds)", 20, 60, 40)
        silent_threshold = st.slider("Silent Threshold (lower = more clips)", 0.01, 0.1, 0.04, 0.01)
        
        # Background video selection
        st.subheader("Background Video")
        background_videos = find_background_videos()
        if background_videos:
            bg_options = ["Automatic", "Dynamic (Random per clip)"] + [video["name"] for video in background_videos]
            selected_bg = st.selectbox("Select background video", bg_options)
            
            if selected_bg == "Automatic":
                st.info("The app will automatically select a background video")
                bg_video_path = None
                use_dynamic = False
            elif selected_bg == "Dynamic (Random per clip)":
                st.info("🎲 Each clip will use a randomly selected background video, starting at a random point!")
                bg_video_path = "dynamic"
                use_dynamic = True
            else:
                for video in background_videos:
                    if video["name"] == selected_bg:
                        bg_video_path = video["path"]
                        st.success(f"✅ Using {selected_bg} as background video")
                        use_dynamic = False
                        break
        else:
            st.error("⚠️ No background videos found! Please add MP4 files to the assets folder.")
            bg_video_path = None
            use_dynamic = False
    
    with col2:
        # Subtitle customization
        st.subheader("Subtitle Settings")
        
        # Style selection dropdown
        style_names = list(SUBTITLE_STYLES.keys())
        selected_style = st.selectbox("Select Subtitle Style", style_names, index=0)
        
        # Get selected style config
        style_config = SUBTITLE_STYLES[selected_style]
        
        # Show style parameters with current values
        subtitle_color = st.color_picker(
            "Subtitle Text Color", 
            f"#{style_config['text_color']}"
        )
        # Remove # from color for internal use
        text_color_hex = subtitle_color.lstrip('#')
        
        subtitle_outline = st.checkbox(
            "Add Text Outline", 
            value=style_config['use_outline']
        )
        
        outline_color = st.color_picker(
            "Outline Color", 
            f"#{style_config['outline_color']}" if style_config['outline_color'] else "#000000"
        ) if subtitle_outline else "#000000"
        # Remove # from color for internal use
        outline_color_hex = outline_color.lstrip('#')
        
        subtitle_size = st.slider(
            "Subtitle Size", 
            8, 48, 
            value=style_config['font_size']
        )
        
        # Build custom style config from UI inputs
        custom_style_config = {
            "font_size": subtitle_size,
            "text_color": text_color_hex,
            "use_outline": subtitle_outline,
            "outline_color": outline_color_hex if subtitle_outline else None
        }
        
        # Preview subtitle style
        subtitle_stroke = "2px 2px 3px #000000" if subtitle_outline else "none"
        st.markdown(
            f"""
            <style>
            :root {{
                --subtitle-color: {subtitle_color};
                --subtitle-stroke: {subtitle_stroke};
            }}
            </style>
            <p>Subtitle Preview:</p>
            <div class="subtitle-preview" style="font-size: {subtitle_size * 1.5}px; color: {subtitle_color}; text-shadow: {subtitle_stroke};">
                This is how your subtitles will look
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Display style description
        st.markdown(f"**Current Style: {selected_style}**")
        
        # Add option to save custom settings as a new style
        if st.button("Apply Custom Settings"):
            # Update the selected style with custom settings
            SUBTITLE_STYLES[selected_style] = custom_style_config
            st.success(f"Updated {selected_style} style with your custom settings!")
        
        # Add option to reset to default style
        if st.button("Reset to Default"):
            # Restore original style
            st.experimental_rerun()
        
        # Video quality settings
        st.subheader("Output Quality")
        video_quality = st.select_slider(
            "Video Quality",
            options=["Low", "Medium", "High", "Very High"],
            value="Medium"
        )
        quality_map = {
            "Low": 28,
            "Medium": 23,
            "High": 18,
            "Very High": 15
        }
        
    st.markdown('</div>', unsafe_allow_html=True)
else:
    # Set default values
    min_clip_duration = 10
    max_clip_duration = 40
    silent_threshold = 0.04
    subtitle_color = "#FFFF00"
    subtitle_outline = True
    outline_color = "#000000"
    subtitle_size = 12
    video_quality = "Medium"
    quality_map = {
        "Low": 28,
        "Medium": 23,
        "High": 18,
        "Very High": 15
    }
    
    # Background video selection (simplified)
    st.subheader("Background Video")
    background_videos = find_background_videos()
    if background_videos:
        bg_options = ["Automatic", "Dynamic (Random per clip)"] + [video["name"] for video in background_videos]
        selected_bg = st.selectbox("Select background video", bg_options)
        
        if selected_bg == "Automatic":
            st.info("The app will automatically select a background video")
            bg_video_path = None
            use_dynamic = False
        elif selected_bg == "Dynamic (Random per clip)":
            st.info("🎲 Each clip will use a randomly selected background video, starting at a random point!")
            bg_video_path = "dynamic"
            use_dynamic = True
        else:
            for video in background_videos:
                if video["name"] == selected_bg:
                    bg_video_path = video["path"]
                    st.success(f"✅ Using {selected_bg} as background video")
                    use_dynamic = False
                    break
    else:
        st.error("⚠️ No background videos found! Please add MP4 files to the assets folder.")
        bg_video_path = None
        use_dynamic = False

# Process button
process_button = st.button("Process YouTube Video", type="primary", disabled=not youtube_url)

# Create a function to process the video using BrainrotWorkflow
async def process_video_with_workflow(url, output_dir, bg_video_path, progress_queue=None, use_dynamic=False, **config):
    """Process a video using BrainrotWorkflow"""
    try:
        # Get the selected style from config
        selected_style = config.get("subtitle_style", "default")
        subtitle_config = config.get("subtitle_config", None)
        
        # Configure the workflow with user settings including subtitle style
        workflow = BrainrotWorkflow(
            output_dir=output_dir,
            subtitle_style=selected_style
        )
        
        # Configure highlight extraction parameters
        workflow.highlight_extractor.min_clip_duration = config.get("min_clip_duration", 10)
        workflow.highlight_extractor.max_clip_duration = config.get("max_clip_duration", 40)
        workflow.highlight_extractor.silent_threshold = config.get("silent_threshold", 0.04)
        
        # Send initial notification to progress queue if available
        if progress_queue:
            await progress_queue.put({"type": "step", "step": 1, "highlight": 0, "description": "Starting download"})
        
        # Process the video with subtitle config and dynamic background setting
        return await workflow.process_video(
            url, 
            bg_video_path, 
            subtitle_config,
            use_dynamic_background=use_dynamic
        )
        
    except Exception as e:
        print(f"Error in workflow: {e}")
        if progress_queue:
            await progress_queue.put({"type": "error", "error": str(e)})
        return []

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
        
        # Add wandering icon feature
        show_wandering_icon()
        
        # Progress section
        st.markdown('<div class="progress-section">', unsafe_allow_html=True)
        st.subheader("Progress")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.markdown('<div class="status-text">Initializing...</div>', unsafe_allow_html=True)
        highlight_counter = st.empty()
        highlight_counter.markdown('<div class="highlight-counter">Getting ready...</div>', unsafe_allow_html=True)
        
        # Add a container for fun loading GIFs
        loading_gif_container = st.empty()
        # Store in session state for reference across functions
        if 'current_gif' not in st.session_state:
            st.session_state.current_gif = random.choice(LOADING_GIFS)
        loading_gif_container.markdown(f'<div style="display:flex; justify-content:center; margin:20px 0;"><img src="{st.session_state.current_gif}" width="200px" /></div>', unsafe_allow_html=True)
        
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
            # Store current GIF in session state to be accessible across functions
            if 'current_gif' not in st.session_state:
                st.session_state.current_gif = random.choice(LOADING_GIFS)
            
            async def update_progress():
                steps = ["Downloading", "Extracting highlights", "Formatting videos", "Transcribing", 
                         "Preparing background", "Adding subtitles", "Creating final videos", "Optimizing"]
                progress_values = [20, 30, 40, 60, 70, 80, 90, 95]
                
                for i, (step, value) in enumerate(zip(steps, progress_values)):
                    progress_text.text(f"{step}...")
                    progress_bar.progress(value)
                    
                    # Update the loading GIF with a new random one
                    new_gif = random.choice([gif for gif in LOADING_GIFS if gif != st.session_state.current_gif])
                    loading_gif_container.markdown(f'<div style="display:flex; justify-content:center; margin:20px 0;"><img src="{new_gif}" width="200px" /></div>', unsafe_allow_html=True)
                    st.session_state.current_gif = new_gif
                    
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
                        elif msg["type"] == "error":
                            st.error(f"Error: {msg['error']}")
                        
                        # Check if we're done
                        if msg.get("done", False) or (total_highlights > 0 and completed_highlights >= total_highlights):
                            break
                
                tracking_task = asyncio.create_task(track_highlights_progress())
                
                # Call process_video with progress updates
                config = {
                    "min_clip_duration": min_clip_duration,
                    "max_clip_duration": max_clip_duration,
                    "silent_threshold": silent_threshold,
                    "subtitle_style": selected_style,  # Pass the style name
                    "subtitle_config": custom_style_config,  # Pass the custom config
                    "crf_value": quality_map[video_quality]
                }
                
                result = await process_video_with_workflow(
                    youtube_url, 
                    run_output_dir, 
                    bg_video_path, 
                    progress_queue,
                    use_dynamic=use_dynamic,
                    **config
                )
                
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
    col_count = 5  # Number of columns in the grid
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
st.markdown("Made with Brainrot by [Ricardo Barroca](https://rbarroca.com) | [GitHub Repo](https://github.com/elbarroca/FR8-Brainrot-Maker)")