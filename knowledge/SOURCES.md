# Knowledge sources and reuse

## Executive summary

VoxPrep HK retrieves the user's job description alongside an original bilingual STAR practice rubric and a small attributed O*NET 31.0 occupational subset. The subset includes 72 original rows from three technology occupations, retaining raw values and a hash of the downloaded archive. O*NET describes work in the United States; it is contextual material, not a claim about a particular Hong Kong employer. Uploaded job text remains untrusted quoted data. Local source text is deleted when its last interview session is deleted.

## Source manifest

| Source | Provenance | License and modifications |
| --- | --- | --- |
| `star-rubric.txt` | Original VoxPrep HK project text, 2026 | Original work; English and Cantonese guidance |
| `onet31-subset.json` | [O*NET 31.0 Database](https://www.onetcenter.org/database.html), U.S. Department of Labor, Employment and Training Administration | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); raw selected rows retained |
| `onet31-*.txt` | Rendered from the subset JSON and O*NET content-model definitions | Selected and reformatted; definitions joined by Element ID; source identifiers retained |
| Uploaded descriptions | User-provided TXT/PDF/DOCX or pasted text | User responsible for permission; kept local, excluded from submission archives |

Downloaded archive: `https://www.onetcenter.org/dl_files/database/db_31_0_text.zip`.

Archive SHA-256: `6883548adf5fde64cf6f801b35d15519c9225f2732c3cab0e281c652d16b23a9`.

Occupations: Software Developers (15-1252.00), Data Scientists (15-2051.00), and Computer and Information Research Scientists (15-1221.00). For each occupation, selection includes the first six task statements and the six highest importance rows in each of Essential Skills, Transferable Skills and Work Activities. Importance numbers are original O*NET scales, not scores assigned to students.

This project includes information from the O*NET® 31.0 Database by USDOL/ETA, used under CC BY 4.0. O*NET® is a trademark of USDOL/ETA. VoxPrep HK has selected and reformatted some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.

## Retrieval behavior

Sources are chunked at approximately 450 token-like units with 80 units of overlap. These are word/CJK/punctuation boundaries, not the model's exact tokenizer. SQLite development mode uses lexical retrieval and optional in-memory cosine ranking. PostgreSQL uses full-text search plus a 1,024-dimensional pgvector HNSW index when local embeddings are configured. Reciprocal-rank fusion combines rankings; the optional local `/rerank` adapter reranks up to 12 candidates before four passages are selected. Missing model services leave lexical retrieval available and are disclosed in health status.

The language model returns source IDs, which the server resolves to original passages. Unknown IDs fail validation and trigger an explicitly labelled deterministic fallback. This validates source identity; it does not prove every generated sentence is entailed by its citation. Citation precision and injection resistance still require the planned human evaluation.
