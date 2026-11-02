# Sources, assets and redistribution

## Executive summary

The application uses locally authored demonstration material, an original procedural avatar, attributed O*NET knowledge and public model artifacts. Model downloads are pinned to revisions and verified by SHA-256. Source packaging excludes base weights, secrets and session databases. Preserve each dependency's license and the O*NET attribution when redistributing. The course PDFs are supplied reference documents, not project-authored content, and are not included in the generated source archive.

## Content and models

| Material | Origin and purpose | License / handling |
| --- | --- | --- |
| Fictional job and STAR rubric | `data/demo-job.txt`, `knowledge/` | Locally authored project material |
| Original 3D interviewer | `frontend/src/components/Avatar.tsx` | Procedurally constructed geometry, no external avatar asset |
| O*NET 31.0 subset | [O*NET database](https://www.onetcenter.org/database.html), exact source manifest in `knowledge/` | Preserve [O*NET attribution and CC BY 4.0 terms](https://www.onetcenter.org/license_db.html) |
| Qwen3-4B-Instruct-2507 | [Qwen model](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Unsloth GGUF conversion](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF) | Apache-2.0; base model, no VoxPrep training implied |
| Qwen3-Embedding-0.6B | [Official GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) | Apache-2.0 |
| Qwen3-Reranker-0.6B | [Qwen model](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [GGUF conversion](https://huggingface.co/gorse-io/Qwen3-Reranker-0.6B-GGUF) | Apache-2.0; community conversion |
| Whisper large-v3-turbo | [whisper.cpp conversions](https://huggingface.co/ggerganov/whisper.cpp) | MIT |
| Training curriculum drafts | `ml/data/` and generator | Synthetic, unreviewed and unsuitable for promotion without review |
| System speech smoke clips | Generated locally with macOS voices | Integration-only fixtures, excluded from source archive |

## Software

React, Vite, Tailwind CSS, Three.js, React Three Fiber, FastAPI and the Azure Speech JavaScript SDK are third-party dependencies. Their installed package notices and lockfiles are the authoritative version-specific license records. The project does not bundle proprietary Azure services or grant rights to their use. PostgreSQL and pgvector are obtained from their official container/package sources. `requirements.lock` and frontend/e2e lockfiles retain application dependency versions; GPU training has a separate pinned environment.

## Provenance rules

Every dataset example must identify its source, authorship, review and language. Do not copy private interview answers into the training corpus. Do not change synthetic examples to “human reviewed” without a real reviewer. Record actual author contributions separately from the proposed division of work. Keep the original course requirements and supplied plan available for verification.
