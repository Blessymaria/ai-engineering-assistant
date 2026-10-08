def run(args, ctx):
    import re

    args = args

    # 1. Find the node details (lines) for the given symbol
    nodes = ctx.list_nodes("function")
    node_info = next((n for n in nodes if n["name"] == args["symbol_name"]), None)

    if not node_info:
        return {"error": f"Could not find node {args['symbol_name']}"}

    file_path = node_info["path"]
    start_line = node_info["line"]
    end_line = node_info["end"]

    # 2. Use git_log_lines to get history specific to these lines
    history = ctx.git_log_lines(file_path, start_line, end_line, limit=args.get("limit", 10))

    # 3. Format the output
    results = []
    for commit in history:
        results.append({
            "commit": commit["commit"],
            "author": commit["author"],
            "date": commit["date"],
            "subject": commit["subject"]
        })

    return {"history": results}
