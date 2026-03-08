variable "DOCKERHUB_REPO" {
  default = "runpod"
}

variable "DOCKERHUB_IMG" {
  default = "worker-v1-vllm"
}

variable "RELEASE_VERSION" {
  default = "latest"
}

variable "CUDA_IMAGE_TAG" {
  default = "12.6.3-devel-ubuntu22.04"
}

variable "PYTORCH_CUDA_INDEX" {
  default = "cu126"
}

variable "VLLM_VERSION" {
  default = "0.16.0"
}

variable "VLLM_NIGHTLY" {
  default = "true"
}

variable "VLLM_NIGHTLY_VERSION" {
  default = "0.17.0rc1.dev149+g40077ea3d"
}

variable "TRANSFORMERS_REF" {
  default = "421c7f6248e28d24d84ee000252a1e71fbc24917"
}

variable "ENABLE_FLASHINFER" {
  default = "true"
}

variable "HUGGINGFACE_ACCESS_TOKEN" {
  default = ""
}

group "default" {
  targets = ["worker-vllm"]
}

target "worker-vllm" {
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}"]
  context = "."
  dockerfile = "Dockerfile"
  platforms = ["linux/amd64"]
  args = {
    CUDA_IMAGE_TAG = "${CUDA_IMAGE_TAG}"
    PYTORCH_CUDA_INDEX = "${PYTORCH_CUDA_INDEX}"
    VLLM_NIGHTLY = "${VLLM_NIGHTLY}"
    VLLM_NIGHTLY_VERSION = "${VLLM_NIGHTLY_VERSION}"
    TRANSFORMERS_REF = "${TRANSFORMERS_REF}"
    VLLM_VERSION = "${VLLM_VERSION}"
    ENABLE_FLASHINFER = "${ENABLE_FLASHINFER}"
  }
}
