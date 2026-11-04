"""Serve the director with TCP rendezvous and a matching CUDA toolchain."""

import os
import runpy
import subprocess
import sys
import sysconfig
from pathlib import Path


def configure_toolkit():
    toolkit = Path(sysconfig.get_paths()["purelib"]) / "nvidia/cu13"
    if not (toolkit / "bin/nvcc").is_file():
        return
    runtime = toolkit / "lib"
    if runtime.is_dir():
        if not (toolkit / "lib64").exists():
            (toolkit / "lib64").symlink_to("lib")
        if not (runtime / "libcudart.so").exists() and (runtime / "libcudart.so.13").exists():
            (runtime / "libcudart.so").symlink_to("libcudart.so.13")
    os.environ["CUDA_HOME"] = str(toolkit)
    os.environ["PATH"] = str(toolkit / "bin") + os.pathsep + os.environ.get("PATH", "")


configure_toolkit()
from vllm.utils import network_utils  # noqa: E402


def tcp_rendezvous():
    return network_utils.get_distributed_init_method(network_utils.get_loopback_ip(), network_utils.get_open_port())


network_utils.get_file_store_init_method = tcp_rendezvous
if __name__ == "__main__":
    # Exercise the JIT toolchain before loading a large checkpoint. The child
    # releases its CUDA context before vLLM creates tensor-parallel workers.
    subprocess.run([sys.executable, "-c", """
import torch
import flashinfer
p = torch.ones(1, 1024, device='cuda') / 1024
result = flashinfer.sampling.top_k_top_p_sampling_from_probs(p, top_k=10, top_p=.9)
torch.cuda.synchronize()
assert result.numel() == 1
print('Director CUDA preflight passed', flush=True)
"""], check=True, timeout=300)
    runpy.run_module("vllm.entrypoints.openai.api_server", run_name="__main__")
