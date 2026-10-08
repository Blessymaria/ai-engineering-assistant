def run(args, ctx):
    import re

    args = args

    # 1. Find the node details (path, line, end) for the given symbol
    node = None
    if args.get("symbol_kind") == "function":
        nodes = [n for n in ctx.list_nodes("function") if n["name"] == args.get("symbol_name")]
    elif args.get("symbol_kind") == "class":
        nodes = [n for n in ctx.list_nodes("class") if n["name"] == args.get("symbol_name")]

    if nodes:
        node = nodes[0]
    else:
        return {"error": f"Symbol {args.get('symbol_name')} of kind {args.get('symbol_kind')} not found."}

    path = node["path"]
    start_line = node["line"]
    end_line = node["end"]

    # 2. Use ctx.git_blame to get line-by-line history for the symbol's range
    blame_data = ctx.git_blame(path, start_line, end_line)

    # 3. Process blame data to summarize history per line
    history_summary = []
    for entry in blame_data:
        history_summary.append({"line": entry["line"], "author": entry["author"], "date": entry["date"], "summary": entry["summary"]})

    # 4. Return the structured history
    return {"symbol": args.get("symbol_name"), "path": path, "history": history_summary}
