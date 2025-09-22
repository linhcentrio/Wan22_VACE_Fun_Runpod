# Wan22 VACE Fun - RunPod Serverless

Dịch vụ RunPod Serverless cho Character Swap sử dụng Wan2.2 VACE Fun workflow. Cho phép thay thế nhân vật trong video bằng hình ảnh nhân vật mong muốn.

## Tính năng

- **Character Swap**: Thay thế nhân vật trong video với hình ảnh tham chiếu
- **VACE Technology**: Sử dụng Video-Aware Character Editing để có kết quả chất lượng cao
- **Segmentation tự động**: Sử dụng SAM2 để tự động phân đoạn nhân vật
- **Color Matching**: Tự động điều chỉnh màu sắc để đồng nhất
- **Flexible Input**: Hỗ trợ nhiều định dạng đầu vào (URL, Base64, File path)
- **Multiple Output**: Hỗ trợ xuất ra MinIO hoặc Base64

## API Input Parameters

### Required Parameters

- **character_image_url** / **character_image_base64** / **character_image_path**: Hình ảnh nhân vật muốn thay thế
- **source_video_url** / **source_video_base64** / **source_video_path**: Video nguồn chứa nhân vật cần thay thế

### Optional Parameters

- **prompt** (string, default: "A woman is walking and smiling at the camera"): Mô tả cho việc tạo video
- **width** (int, default: 480): Chiều rộng video đầu ra
- **height** (int, default: 848): Chiều cao video đầu ra
- **total_steps** (int, default: 6): Tổng số bước sampling
- **split_step** (int, default: 3): Bước chia giữa high-noise và low-noise model
- **output_format** (string, default: "minio"): Định dạng đầu ra ("minio" hoặc "base64")
- **points_positive** (array): Điểm segmentation tùy chỉnh (nếu không có sẽ dùng mặc định)

## Example API Call

```json
{
  "input": {
    "character_image_url": "https://example.com/character.jpg",
    "source_video_url": "https://example.com/source_video.mp4",
    "prompt": "A person walking gracefully in a park",
    "width": 480,
    "height": 848,
    "total_steps": 6,
    "split_step": 3,
    "output_format": "minio"
  }
}
```

## Example với Base64

```json
{
  "input": {
    "character_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...",
    "source_video_base64": "data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb2...",
    "prompt": "A beautiful woman dancing elegantly",
    "output_format": "base64"
  }
}
```

## Response Format

### Success Response (MinIO)
```json
{
  "video_url": "https://media.aiclip.ai/video/vace_fun_task_12345678_abcdef12.mp4",
  "output_format": "minio",
  "status": "completed"
}
```

### Success Response (Base64)
```json
{
  "video_base64": "AAAAIGZ0eXBpc29tAAACAGlzb2...",
  "output_format": "base64",
  "status": "completed"
}
```

### Error Response
```json
{
  "error": "Character image input이 필요합니다 (character_image_path, character_image_url, 또는 character_image_base64)"
}
```

## Workflow Details

Dịch vụ này sử dụng workflow Wan22_VACE_Fun_Character_Swap_Workflow.json với các bước chính:

1. **Load Input**: Tải hình ảnh nhân vật và video nguồn
2. **Segmentation**: Sử dụng SAM2 để phân đoạn nhân vật trong video
3. **VACE Encoding**: Mã hóa video với thông tin nhân vật tham chiếu
4. **Two-stage Sampling**: 
   - High-noise model (steps 0 → split_step)
   - Low-noise model (split_step → total_steps)
5. **Color Matching**: Điều chỉnh màu sắc đầu ra
6. **Video Output**: Xuất video kết quả

## Requirements

- GPU: NVIDIA ADA_24 hoặc ADA_32_PRO
- VRAM: Tối thiểu 24GB
- Container Disk: 50GB
- CUDA: 12.8+

## Custom Segmentation Points

Nếu muốn tùy chỉnh điểm segmentation, có thể truyền `points_positive`:

```json
{
  "input": {
    "character_image_url": "https://example.com/character.jpg",
    "source_video_url": "https://example.com/source_video.mp4",
    "points_positive": [
      {"x": 200, "y": 150},
      {"x": 160, "y": 580},
      {"x": 100, "y": 250}
    ]
  }
}
```

## Performance Tips

- Sử dụng video có độ phân giải gần với target resolution để có kết quả tốt nhất
- Hình ảnh nhân vật nên có chất lượng cao và rõ nét
- Với video dài, có thể cần tăng timeout
- Sử dụng `output_format: "minio"` để tiết kiệm băng thông với video lớn

## Model Information

- **Base Model**: Wan2.2 T2V (GGUF Q4_K_M quantized)
- **VACE Modules**: Wan2.2 Fun VACE (High & Low noise)
- **Text Encoder**: UMT5-XXL (FP8 scaled)
- **VAE**: Wan2.1 VAE
- **Segmentation**: SAM2.1 Hiera Small
- **Speed LoRA**: LightX2V distilled LoRA
