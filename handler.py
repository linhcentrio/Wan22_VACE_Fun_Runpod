import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii
import subprocess
import time
from minio import Minio
from urllib.parse import quote

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MinIO Configuration
MINIO_ENDPOINT = "media.aiclip.ai"
MINIO_ACCESS_KEY = "VtZ6MUPfyTOH3qSiohA2"
MINIO_SECRET_KEY = "8boVPVIynLEKcgXirrcePxvjSk7gReIDD9pwto3t"
MINIO_BUCKET = "video"
MINIO_SECURE = False

# Initialize MinIO client with error handling
try:
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    logger.info("✅ MinIO client initialized")
except Exception as e:
    logger.error(f"❌ MinIO initialization failed: {e}")
    minio_client = None

server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', '--timeout=30', url
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")

def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        if base64_data.startswith("data:"):
            base64_data = base64_data.split(",", 1)[1]
        
        missing_padding = len(base64_data) % 4
        if missing_padding:
            base64_data += '=' * (4 - missing_padding)
        
        decoded_data = base64.b64decode(base64_data)
        os.makedirs(temp_dir, exist_ok=True)
        
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")

def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 파일 경로를 반환하는 함수"""
    if input_type == "path":
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return input_data
    elif input_type == "url":
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        logger.info(f"🔢 Base64 입력 처리")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                with open(video['fullpath'], 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def upload_to_minio(local_path: str, object_name: str) -> str:
    """Upload file to MinIO storage với error handling"""
    try:
        if not minio_client:
            raise RuntimeError("MinIO client not initialized")
        
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
        logger.info(f"📤 Uploading to MinIO: {object_name} ({file_size_mb:.1f}MB)")
        
        minio_client.fput_object(MINIO_BUCKET, object_name, local_path)
        
        file_url = f"https://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{quote(object_name)}"
        logger.info(f"✅ Upload completed: {file_url}")
        
        return file_url
        
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        raise e

def handler(job):
    job_input = job.get("input", {})
    logger.info(f"Received job input: {job_input}")
    
    task_id = f"task_{uuid.uuid4()}"
    
    # Character image input 처리
    character_image_path = None
    if "character_image_path" in job_input:
        character_image_path = process_input(job_input["character_image_path"], task_id, "character_image.png", "path")
    elif "character_image_url" in job_input:
        character_image_path = process_input(job_input["character_image_url"], task_id, "character_image.png", "url")
    elif "character_image_base64" in job_input:
        character_image_path = process_input(job_input["character_image_base64"], task_id, "character_image.png", "base64")
    else:
        return {"error": "Character image input이 필요합니다 (character_image_path, character_image_url, 또는 character_image_base64)"}
    
    # Source video input 처리
    source_video_path = None
    if "source_video_path" in job_input:
        source_video_path = process_input(job_input["source_video_path"], task_id, "source_video.mp4", "path")
    elif "source_video_url" in job_input:
        source_video_path = process_input(job_input["source_video_url"], task_id, "source_video.mp4", "url")
    elif "source_video_base64" in job_input:
        source_video_path = process_input(job_input["source_video_base64"], task_id, "source_video.mp4", "base64")
    else:
        return {"error": "Source video input이 필요합니다 (source_video_path, source_video_url, 또는 source_video_base64)"}
    
    # 파일 존재 확인
    if not os.path.exists(character_image_path):
        return {"error": f"Character image 파일을 찾을 수 없습니다: {character_image_path}"}
    if not os.path.exists(source_video_path):
        return {"error": f"Source video 파일을 찾을 수 없습니다: {source_video_path}"}
    
    # Parameters
    prompt_text = job_input.get("prompt", "A woman is walking and smiling at the camera")
    width = job_input.get("width", 480)
    height = job_input.get("height", 848)
    total_steps = job_input.get("total_steps", 6)
    split_step = job_input.get("split_step", 3)
    output_format = job_input.get("output_format", "minio")
    
    # Segmentation points - 사용자가 제공하지 않으면 기본값 사용
    points_positive = job_input.get("points_positive", [
        {"x": 203.51, "y": 125.91},
        {"x": 161.05, "y": 581.25},
        {"x": 106.88, "y": 253.29}
    ])
    
    # Validate output_format
    if output_format not in ["minio", "base64"]:
        logger.error(f"❌ Invalid output_format: {output_format}")
        return {"error": "output_format must be either 'minio' or 'base64'"}
    
    logger.info(f"📤 Output format: {output_format}")
    logger.info(f"Character image: {character_image_path}")
    logger.info(f"Source video: {source_video_path}")
    
    # Load workflow
    workflow_file = "/Wan22_VACE_Fun_Character_Swap_Workflow.json"
    prompt = load_workflow(workflow_file)
    
    # Configure workflow nodes
    # Character image (node 58)
    prompt["58"]["inputs"]["image"] = os.path.basename(character_image_path)
    
    # Source video (node 119)
    prompt["119"]["inputs"]["video"] = os.path.basename(source_video_path)
    
    # Text prompt (node 49)
    prompt["49"]["inputs"]["text"] = prompt_text
    
    # Dimensions (nodes 153, 154)
    prompt["153"]["inputs"]["value"] = width
    prompt["154"]["inputs"]["value"] = height
    
    # Steps (nodes 127, 130)
    prompt["127"]["inputs"]["value"] = split_step
    prompt["130"]["inputs"]["value"] = total_steps
    
    # Segmentation points (node 174)
    points_store = {
        "positive": points_positive,
        "negative": [{"x": 0, "y": 0}]
    }
    coordinates = json.dumps(points_positive)
    neg_coordinates = json.dumps([{"x": 0, "y": 0}])
    
    prompt["174"]["inputs"]["points_store"] = json.dumps(points_store)
    prompt["174"]["inputs"]["coordinates"] = coordinates
    prompt["174"]["inputs"]["neg_coordinates"] = neg_coordinates
    prompt["174"]["inputs"]["width"] = width
    prompt["174"]["inputs"]["height"] = height
    
    # Copy files to ComfyUI input directory
    import shutil
    comfyui_input_dir = "/ComfyUI/input"
    os.makedirs(comfyui_input_dir, exist_ok=True)
    
    shutil.copy2(character_image_path, os.path.join(comfyui_input_dir, os.path.basename(character_image_path)))
    shutil.copy2(source_video_path, os.path.join(comfyui_input_dir, os.path.basename(source_video_path)))
    
    # Connect to WebSocket and process
    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # HTTP 연결 확인
    http_url = f"http://{server_address}:8188/"
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    max_attempts = 36  # 3분
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과")
            time.sleep(5)
    
    videos = get_videos(ws, prompt)
    ws.close()
    
    # 비디오 처리 및 출력
    for node_id in videos:
        if videos[node_id]:
            temp_video_path = f"/tmp/vace_fun_{uuid.uuid4().hex[:8]}.mp4"
            try:
                with open(temp_video_path, 'wb') as f:
                    f.write(base64.b64decode(videos[node_id][0]))
                
                if output_format == "base64":
                    logger.info("🔢 Returning video as base64...")
                    return {
                        "video_base64": videos[node_id][0],
                        "output_format": "base64",
                        "status": "completed"
                    }
                else:
                    logger.info("📤 Uploading video to MinIO...")
                    output_filename = f"vace_fun_{task_id}_{uuid.uuid4().hex[:8]}.mp4"
                    try:
                        video_url = upload_to_minio(temp_video_path, output_filename)
                        
                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
                        
                        return {
                            "video_url": video_url,
                            "output_format": "minio",
                            "status": "completed"
                        }
                    except Exception as e:
                        logger.error(f"❌ MinIO upload failed: {e}")
                        logger.info("🔄 Falling back to base64 output...")
                        return {
                            "video_base64": videos[node_id][0],
                            "output_format": "base64",
                            "status": "completed",
                            "warning": f"MinIO upload failed, returned base64: {str(e)}"
                        }
                        
            except Exception as e:
                logger.error(f"❌ Video processing failed: {e}")
                return {"error": f"비디오 처리 중 오류 발생: {str(e)}"}
            finally:
                if os.path.exists(temp_video_path):
                    try:
                        os.remove(temp_video_path)
                    except:
                        pass
    
    return {"error": "비디오를 찾을 수 없습니다."}

runpod.serverless.start({"handler": handler})
