def run(args, ctx):
    import re

    symbol_name = args.get("symbol_name")
    symbol_kind = args.get("symbol_kind")

    if not all([symbol_name, symbol_kind]):
        return {"error": "Missing required arguments: symbol_name and symbol_kind must be provided."}

    # 1. Find the node details (path, line, end) using list_nodes
    nodes = ctx.list_nodes(symbol_kind)
    node_info = next((n for n in nodes if n["name"] == symbol_name), None)

    if not node_info:
        return {"error": f"Symbol {symbol_name} of kind {symbol_kind} not found. Check symbol name or kind."}

    file_path = node_info["path"]
    start_line = node_info["line"]
    end_line = node_info["end"]

    # 2. Use git_log_lines to get commits affecting this specific range
    history = ctx.git_log_lines(file_path, start_line, end_line, limit=10)

    # 3. Format the output
    formatted_history = []
    for commit in history:
        formatted_history.append({
            "commit": commit.get("commit"),
            "author": commit.get("author"),
            "date": commit.get("date"),
            "subject": commit.get("subject")
        })

    return {"symbol": symbol_name, "file": file_path, "history": formatted_history}
