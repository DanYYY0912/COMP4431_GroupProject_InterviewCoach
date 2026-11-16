"""Human relevance labelling plus measured retrieval metrics.

Nothing here may invent a label. A label exists only because a person typed a
reviewer name and pressed a key, and ``reviewed_by`` is copied from those names
and nowhere else.
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from evaluation.metrics import citation_precision, recall_at_k
from ml.dataset import read_jsonl
from ml.review import atomic_write, parse_shard, reviewer_name, shard_rows, slug

DEFAULT_CORPUS = Path("evaluation/fixtures/retrieval_corpus.jsonl")
DEFAULT_QUERIES = Path("evaluation/fixtures/retrieval_queries.jsonl")
DEFAULT_LABELS = Path("evaluation/fixtures/retrieval_labels")
DEFAULT_INPUT = Path("evaluation/fixtures/retrieval_queries_reviewed.jsonl")
DEFAULT_RESULTS = Path("evaluation/results/retrieval_metrics.json")
TOP_K = 5
DISPLAY_CHARS = 300
COMMANDS = ("label", "merge", "score")
HELP = (
    "numbers toggle a mark · a = accept marked · all = accept all five · "
    "n = none relevant · s = skip · q = quit"
)


def label_path(directory, reviewer):
    """One file per reviewer identity; the slug binds the name to the file."""
    return Path(directory) / f"{slug(reviewer)}.jsonl"


def _moment(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"Unparseable labelled_at: {value!r}") from None


def load_labels(directory):
    """Read every label file, refusing anything a human could not have written."""
    records = []
    for path in sorted(Path(directory).glob("*.jsonl")):
        for record in read_jsonl(path):
            query_id = record.get("query_id")
            reviewer = reviewer_name(record.get("reviewer") or "")
            relevant = record.get("relevant_ids")
            if not isinstance(query_id, str) or not query_id:
                raise ValueError(f"{path.name}: label without a query_id")
            if not isinstance(relevant, list) or any(
                not isinstance(chunk_id, str) or not chunk_id for chunk_id in relevant
            ):
                raise ValueError(f"{path.name}: relevant_ids must be chunk ID strings")
            if len(set(relevant)) != len(relevant):
                raise ValueError(f"{path.name}: {query_id} repeats a relevant ID")
            if path.stem != slug(reviewer):
                raise ValueError(
                    f"{path.name}: signed by {reviewer!r}, which is not this file's"
                    " reviewer; labels must stay in the reviewer's own file"
                )
            _moment(record["labelled_at"])
            records.append(
                {
                    "query_id": query_id,
                    "reviewer": reviewer,
                    "relevant_ids": list(relevant),
                    "labelled_at": record["labelled_at"],
                }
            )
    return records


def latest_labels(records):
    """A reviewer's later session replaces that reviewer's earlier label."""
    newest = {}
    for record in records:
        key = (record["query_id"], record["reviewer"].casefold())
        previous = newest.get(key)
        if previous is None or _moment(record["labelled_at"]) >= _moment(
            previous["labelled_at"]
        ):
            newest[key] = record
    by_query = {}
    for record in newest.values():
        by_query.setdefault(record["query_id"], []).append(record)
    for entries in by_query.values():
        entries.sort(key=lambda entry: entry["reviewer"].casefold())
    return by_query


def record_label(labels_dir, reviewer, query_id, relevant_ids):
    """Persist one human decision; the only writer of label files."""
    reviewer = reviewer_name(reviewer)
    record = {
        "query_id": query_id,
        "reviewer": reviewer,
        "relevant_ids": list(dict.fromkeys(relevant_ids)),
        "labelled_at": datetime.now(UTC).isoformat(),
    }
    path = label_path(labels_dir, reviewer)
    kept = [
        existing
        for existing in (read_jsonl(path) if path.exists() else [])
        if existing.get("query_id") != query_id
    ]
    atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in [*kept, record]
        ),
    )
    return record


def merge_rows(queries, labels, output):
    """Refuse to write anything until every query carries a human label."""
    labelled = latest_labels(labels)
    if not labelled:
        raise ValueError("No human labels found; label the shards before merging")
    known = {query["id"] for query in queries}
    unknown = sorted(set(labelled) - known)
    if unknown:
        raise ValueError(f"Labels name queries absent from the fixture: {unknown[:3]}")
    missing = [query["id"] for query in queries if query["id"] not in labelled]
    if missing:
        raise ValueError(
            f"{len(missing)} of {len(queries)} queries have no human label"
            f" (for example {missing[0]}); refusing to write {output}"
        )
    rows = []
    for query in queries:
        entries = labelled[query["id"]]
        row = dict(query)
        row["synthetic_relevant_ids"] = list(query.get("relevant_ids") or [])
        row["relevant_ids"] = sorted(
            {chunk_id for entry in entries for chunk_id in entry["relevant_ids"]}
        )
        row["reviewed_by"] = [entry["reviewer"] for entry in entries]
        row["labels"] = entries
        row["status"] = "human_labelled"
        rows.append(row)
    atomic_write(
        output,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )
    return rows


async def app_retriever(queries, corpus, limit=TOP_K):
    """The application's own retrieval path on the fixture corpus, offline."""
    from backend.app.config import Settings
    from backend.app.db import Base, ChunkRecord, make_database
    from backend.app.retrieval import index_chunks, retrieve

    engine, factory = make_database("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # Lexical path only: four reviewers must measure one identical configuration.
    settings = Settings(
        database_url="sqlite:///:memory:", embedding_base_url="", _env_file=None
    )
    found = {}
    try:
        with factory() as db:
            chunks = [
                ChunkRecord(
                    id=row["id"],
                    source=row["source"],
                    text=row["text"],
                    job_profile_id=None,
                    embedding=None,
                )
                for row in corpus
            ]
            db.add_all(chunks)
            db.commit()
            await index_chunks(db, chunks, settings)
            for query in queries:
                passages = await retrieve(
                    db, "evaluation", query["query"], settings, limit=limit
                )
                found[query["id"]] = [
                    {"id": p.chunk_id, "text": p.text, "source": p.source}
                    for p in passages
                ]
    finally:
        engine.dispose()
    return found


def interpret(marks, text, count):
    """Turn one typed line into marked positions plus at most one action."""
    marks = set(marks)
    action = None
    for token in re.split(r"[,\s]+", text.strip().casefold()):
        if not token:
            continue
        if token.isdigit():
            number = int(token)
            if not 1 <= number <= count:
                raise ValueError(f"Chunk numbers run from 1 to {count}")
            marks.symmetric_difference_update({number})
        elif token in ("a", "accept"):
            action = "accept"
        elif token in ("all", "*"):
            action = "all"
        elif token in ("n", "none"):
            action = "none"
        elif token in ("s", "skip"):
            action = "skip"
        elif token in ("q", "quit"):
            action = "quit"
        else:
            raise ValueError(f"Unknown input {token!r}. {HELP}")
    return marks, action


def render(query, passages, marks, position, total):
    lines = [
        "",
        "─" * 78,
        f"[{position}/{total}] {query['id']}  ({query.get('language', '?')})",
        f"QUERY: {query['query']}",
        "",
    ]
    if not passages:
        lines.append("  (the retrieval path returned nothing for this query)")
    for number, passage in enumerate(passages, 1):
        text = passage["text"]
        if len(text) > DISPLAY_CHARS:
            text = text[:DISPLAY_CHARS] + " …"
        lines.append(
            f"  {'[*]' if number in marks else '[ ]'} {number}  {passage['id']}"
        )
        lines.append(f"        {text}")
    lines += ["", HELP]
    return "\n".join(lines)


def label_session(args, ask=input, retriever=app_retriever):
    """Show real retrieval output and record what a human says answers the query."""
    reviewer = reviewer_name(args.reviewer)
    parse_shard(args.shard)
    queries = read_jsonl(args.queries)
    corpus = read_jsonl(args.corpus)
    mine = shard_rows(queries, args.shard)
    already = {
        label["query_id"]
        for label in load_labels(args.labels_dir)
        if label["reviewer"].casefold() == reviewer.casefold()
    }
    pending = [query for query in mine if query["id"] not in already]
    if args.limit:
        pending = pending[: args.limit]
    if not pending:
        print(f"Nothing left to label for {reviewer} in shard {args.shard}.")
        return 0
    found = asyncio.run(retriever(pending, corpus))
    print(
        f"{len(pending)} of {len(mine)} queries in shard {args.shard} for {reviewer};"
        f" saving to {label_path(args.labels_dir, reviewer)}"
    )
    labelled = 0
    for position, query in enumerate(pending, 1):
        passages = found.get(query["id"], [])
        marks = set()
        while True:
            print(render(query, passages, marks, position, len(pending)))
            try:
                text = ask("> ")
            except EOFError:
                print("\nStopped; saved labels are kept. Rerun to continue.")
                return labelled
            try:
                marks, action = interpret(marks, text, len(passages))
            except ValueError as exc:
                print(f"  {exc}")
                continue
            if action is None:
                continue
            if action == "quit":
                print("Stopped; saved labels are kept. Rerun to continue.")
                return labelled
            if action == "skip":
                break
            if action == "none":
                chosen = []
            elif action == "all":
                chosen = [passage["id"] for passage in passages]
            else:
                if not marks:
                    print("  Nothing marked — type numbers, or 'all', or 'n'.")
                    continue
                chosen = [
                    passage["id"]
                    for number, passage in enumerate(passages, 1)
                    if number in marks
                ]
            record_label(args.labels_dir, reviewer, query["id"], chosen)
            labelled += 1
            break
    print(
        f"Labelled {labelled} this session; file {label_path(args.labels_dir, reviewer)}"
    )
    return labelled


async def score(input_path, corpus, output, retriever=None, corpus_path=None):
    """Measure recall@5 and citation precision against human relevance labels."""
    rows = read_jsonl(input_path)
    if not rows:
        raise ValueError("Reviewed queries are empty")
    unreviewed = [row["id"] for row in rows if not row.get("reviewed_by")]
    if unreviewed:
        raise ValueError(
            f"{len(unreviewed)} queries have no reviewer (for example {unreviewed[0]});"
            " run merge first"
        )
    known = {row["id"] for row in corpus}
    for row in rows:
        unknown = sorted(set(row.get("relevant_ids") or []) - known)
        if unknown:
            raise ValueError(
                f"{row['id']}: relevant IDs absent from the corpus: {unknown}"
            )
    found = await (retriever or app_retriever)(rows, corpus)
    records = []
    for row in rows:
        retrieved = [passage["id"] for passage in found.get(row["id"], [])][:TOP_K]
        relevant = list(row.get("relevant_ids") or [])
        # No relevant passage labelled means the query cannot enter the denominator.
        recall = recall_at_k(retrieved, relevant, TOP_K) if relevant else None
        cited = list(row.get("cited_ids") or retrieved)
        supporting = list(row.get("supported_citation_ids") or relevant)
        precision = citation_precision(cited, supporting) if supporting else None
        records.append(
            {
                "id": row["id"],
                "query": row["query"],
                "retrieved_ids": retrieved,
                "relevant_ids": relevant,
                "recall_at_5": recall,
                "cited_ids": cited,
                "supported_citation_ids": supporting,
                "citation_precision": precision,
            }
        )
    recalled = [record for record in records if record["recall_at_5"] is not None]
    precise = [record for record in records if record["citation_precision"] is not None]
    reviewers = sorted({name for row in rows for name in row["reviewed_by"]})
    summary = {
        "recall_at_5": round(
            sum(record["recall_at_5"] for record in recalled) / len(recalled), 4
        )
        if recalled
        else None,
        "recall_at_5_denominator": len(recalled),
        "citation_precision": round(
            sum(record["citation_precision"] for record in precise) / len(precise), 4
        )
        if precise
        else None,
        "citation_precision_denominator": len(precise),
        "queries": len(records),
    }
    result = {
        "metric": "retrieval",
        "status": "measured",
        "label_source": "human_relevance_labels",
        "date": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "reviewers": reviewers,
        "reviewer_count": len(reviewers),
        "input": str(input_path),
        "corpus": str(corpus_path) if corpus_path else "in-memory fixture corpus",
        "corpus_chunks": len(corpus),
        "k": TOP_K,
        "retriever": (
            "backend.app.retrieval.retrieve on isolated sqlite, lexical path only"
        ),
        "summary": summary,
        "records": records,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    label = sub.add_parser("label", help="Mark which retrieved passages answer a query")
    label.add_argument("--reviewer", required=True, help="Your real name")
    label.add_argument("--shard", default="1/1", help="N/T, one shard per reviewer")
    label.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    label.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    label.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS)
    label.add_argument(
        "--limit", type=int, default=0, help="Stop after N queries (dry runs only)"
    )
    merge = sub.add_parser("merge", help="Merge reviewer labels; refuse if incomplete")
    merge.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    merge.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS)
    merge.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    run = sub.add_parser("score", help="Measure recall@5 and citation precision")
    run.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    run.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    run.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in (*COMMANDS, "-h", "--help"):
        argv = ["label", *argv]
    elif not argv:
        argv = ["label", "-h"]
    args = build_parser().parse_args(argv)
    try:
        if args.command == "label":
            label_session(args)
            return
        if args.command == "merge":
            rows = merge_rows(
                read_jsonl(args.queries), load_labels(args.labels_dir), args.output
            )
            unreachable = [row["id"] for row in rows if not row["relevant_ids"]]
            print(
                f"Merged {len(rows)} human-labelled queries into {args.output};"
                f" reviewers {sorted({n for row in rows for n in row['reviewed_by']})}"
            )
            if unreachable:
                print(
                    f"Warning: {len(unreachable)} queries were labelled as unanswerable"
                    " and stay outside the recall denominator."
                )
            return
        result = asyncio.run(
            score(
                args.input,
                read_jsonl(args.corpus),
                args.output,
                corpus_path=args.corpus,
            )
        )
        summary = result["summary"]
        print(
            f"recall@{TOP_K} = {summary['recall_at_5']}"
            f" over {summary['recall_at_5_denominator']} labelled queries;"
            f" citation precision = {summary['citation_precision']}"
            f" over {summary['citation_precision_denominator']}"
        )
        print(f"Reviewers: {', '.join(result['reviewers'])}; wrote {args.output}")
    except KeyboardInterrupt:
        sys.exit("Stopped; saved labels are kept. Rerun the same command to resume.")
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f"{exc}")


if __name__ == "__main__":
    main()
