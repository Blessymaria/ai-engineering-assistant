def run(args, ctx):
    import re

    # 1. Find the node details (path, start, end) for the target_name
    nodes = ctx.list_nodes("function")
    node_info = next(((n for n in nodes if n["name"] == args.get("target_name") and n.get("path"))), None)

    if not node_info:
        return {"error": f"Could not find node named {args.get("target_name")}"}

    path = node_info["path"]
    start = node_info.get("line", 1)
    end = node_info.get("end", 1000) # Use a large number if end is not available

    # 2. Use git_blame to get line-by-line history for the relevant range
    blame_results = ctx.git_blame(path, start, end)

    # 3. Aggregate the results to find the most recent change for the whole block
    # Since blame gives line-by-line, we'll find the latest commit across all lines.
    # We'll use the commit date from the first entry as a proxy for the block's last change.

    if not blame_results:
        return {"message": "No blame information found for this range."}

    # Sort by date (ISO format allows string comparison)
    latest_commit = max(blame_results, key=lambda x: x.get("date", "0000-00-00"))

    return {
        "function_name": args.get("target_name"),
        "file_path": path,
        "last_changed_date": latest_commit.get("date"),
        "last_changed_author": latest_commit.get("author"),
        "summary": latest_commit.get("summary")
    }
