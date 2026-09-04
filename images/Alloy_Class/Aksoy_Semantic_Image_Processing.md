Hi all,

We've been getting requests for semantic image processing, which is useful for tasks like crack detection, defect characterization, and analyzing technical drawings. With the new update, the vision endpoint now accepts multiple images when using Vision Language Models (VLMs) (thanks to @Brown, Craig D for bringing this up). This enables several benefits:

1.  You can now compare multiple images semantically (shapes, objects, patterns, context).
2.  For many classification tasks (defect categorization, product types, visual inspection), this is often sufficient (sometimes even better) than pixel-level comparison, because VLMs understand context.

With that said, if you need pixel-level similarity (e.g., thin segmentation masks or overlay comparisons), you likely need a different approach entirely: image embeddings via CLIP/SigLIP with cosine similarity, or classical computer vision techniques (SSIM, template matching, feature matching). The vision encoder (typically a vision transformer) handles this differently by splitting the image into fixed-size patches (e.g., 32×32 or 16×16 pixels). Each patch is projected into a high-dimensional embedding vector, producing a sequence of image tokens, similar to how text is tokenized. These image embeddings are then linearly projected into the same embedding space as the language model’s text tokens. The projected image tokens are concatenated with text tokens and fed into the transformer decoder (the same LLM that processes text). The model attends jointly over both image and text tokens. This is why it can reason about semantic relationships, but can’t perform pixel-level distance metrics (MSE, SSIM, histogram correlation, etc.). 

Here are the release notes for more information:

Alloy Server - Version 1.2.17
Feature Release - Multi-image vision endpoint support.

Changes:
•	Multi-Image Vision: The /api/vision endpoint now accepts multiple images in a single request via the new images field (list of base64 strings). Uses the standard OpenAI multi-image content format under the hood. Enables image comparison, classification against references, and batch visual analysis.
•	Backward Compatible: Existing single-image requests using image_base64 continue to work unchanged.
•	Client Updated: alloy.core.llm.image() now accepts a list of file paths or base64 strings for multi-image analysis.
•	Tests & Docs: Added multi-image pytest tests, script-mode tests, and updated the Lesson 5 vision notebook with multi-image examples.

API Usage:
// Single image (unchanged)
{"image_base64": "<base64>", "prompt": "Describe this image."}

// Multiple images (new)
{"images": ["<base64_1>", "<base64_2>", "<base64_3>"], "prompt": "Compare these images."}
