"""NeoLex embedding layer.

Default backend: llama-server (Qwen3-Embedding-8B Q4_K_M via llama.cpp).

Setup:
    1. Download the model (~4.3 GB):
           huggingface-cli download Qwen/Qwen3-Embedding-8B-GGUF \\
               Qwen3-Embedding-8B-Q4_K_M.gguf --local-dir models/

    2. Start llama-server (keep running in background):
           llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
               --embedding --pooling last -ngl 99 -c 4096 --port 8088

    3. Set EMBEDDING_MODEL=llama-server in your .env (already the default).

Fallback: set EMBEDDING_MODEL=snowflake for Snowflake Arctic Embed L v2.0
(no server required, lower quality).
"""
