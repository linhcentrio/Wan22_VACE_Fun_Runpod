# Use specific version of nvidia cuda image
FROM wlsdml1114/multitalk-base:1.4 as runtime

# wget 설치 (URL 다운로드를 위해)
RUN apt-get update && apt-get install -y wget aria2 && rm -rf /var/lib/apt/lists/*

RUN pip install -U "huggingface_hub[hf_transfer]"
RUN pip install runpod websocket-client minio
RUN pip install av spandrel albumentations onnx opencv-python onnxruntime-gpu color-matcher

WORKDIR /

# Clone and setup ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install -r requirements.txt

# Install custom nodes for VACE workflow
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone --branch forQwen https://github.com/Isi-dev/ComfyUI_GGUF.git && \
    cd ComfyUI_GGUF && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Isi-dev/ComfyUI_DeleteModelPassthrough.git && \
    cd ComfyUI_DeleteModelPassthrough && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Isi-dev/comfyui_controlnet_aux && \
    cd comfyui_controlnet_aux && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-KJNodes.git && \
    cd ComfyUI-KJNodes && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-segment-anything-2

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-Florence2 && \
    cd ComfyUI-Florence2 && \
    pip install -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/john-mnz/ComfyUI-Inspyrenet-Rembg.git && \
    cd ComfyUI-Inspyrenet-Rembg && \
    pip install -r requirements.txt

# Download required models for VACE workflow
# Download GGUF models (quan trọng cho VACE)
RUN wget -q https://huggingface.co/bullerwins/Wan2.2-T2V-A14B-GGUF/resolve/main/wan2.2_t2v_high_noise_14B_Q4_K_M.gguf -O /ComfyUI/models/diffusion_models/wan2.2_t2v_high_noise_14B_Q4_K_M.gguf
RUN wget -q https://huggingface.co/bullerwins/Wan2.2-T2V-A14B-GGUF/resolve/main/wan2.2_t2v_low_noise_14B_Q4_K_M.gguf -O /ComfyUI/models/diffusion_models/wan2.2_t2v_low_noise_14B_Q4_K_M.gguf

# Download VACE modules (cốt lõi của workflow)
RUN wget -q https://huggingface.co/Kijai/WanVideo_comfy_GGUF/resolve/main/VACE/Wan2_2_Fun_VACE_module_A14B_HIGH_Q4_K_M.gguf -O /ComfyUI/models/diffusion_models/Wan2_2_Fun_VACE_module_A14B_HIGH_Q4_K_M.gguf
RUN wget -q https://huggingface.co/Kijai/WanVideo_comfy_GGUF/resolve/main/VACE/Wan2_2_Fun_VACE_module_A14B_LOW_Q4_K_M.gguf -O /ComfyUI/models/diffusion_models/Wan2_2_Fun_VACE_module_A14B_LOW_Q4_K_M.gguf

# Download text encoder and VAE
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors -O /ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors -O /ComfyUI/models/vae/wan_2.1_vae.safetensors

# Download speed LoRAs
RUN wget -q https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank32_bf16.safetensors -O /ComfyUI/models/loras/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank32_bf16.safetensors

# Download SAM2 model for segmentation
RUN wget -q https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2.1_hiera_small.safetensors -O /ComfyUI/models/sam2/sam2.1_hiera_small.safetensors

COPY . .
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]

