"""NeoLex embedding layer — pluggable embedder backends.

Recommended setup
-----------------
1. Download the GGUF model:
       huggingface-cli download Qwen/Qwen3-Embedding-8B-GGUF \\
           Qwen3-Embedding-8B-Q4_K_M.gguf --local-dir models/

2. Start llama-server (keep it running in the background):
       llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
           --embedding --pooling last -ngl 99 -c 4096 --port 8088

3. Set EMBEDDING_MODEL=llama-server in your .env.

4. Call `neolex.embeddings.adapter.activate()` before loading the arlc
   pipeline — this pre-sets the singleton so arlc.retriever never tries to
   load a SentenceTransformer.

For "snowflake" (default) no setup is needed and activate() is a no-op.
"""
