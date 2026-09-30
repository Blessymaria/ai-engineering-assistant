def run(args, ctx):
    import re

    # Assuming the agent input format is 'git log -- function <function_name> in <file_path>' 
    # We need to extract the function name and its path/context from the agent's input.
    # Given the example input structure, we'll assume the agent passes the function name and the context is derived from the node list.

    # For this specific tool, we rely on the agent passing the function name and we must find its location.
    # We'll use the function name provided in args['function_name'] and search for it.

    func_name = args.get("function_name")
    if not func_name:
        return {"error": "Function name is required."}

    # 1. Find the node(s) corresponding to the function name
    nodes = []
    for node in ctx.list_nodes("function"):
        if node["name"] == func_name:
            nodes.append(node)

    if not nodes:
        return {"error": f"Function '{func_name}' not found in the repository."}

    # For simplicity, we take the first found node's path as the primary location.
    # In a real scenario, we might need to aggregate results if the function appears multiple times.
    target_path = nodes[0]["path"]

    # 2. Use ctx.git_blame to get line-by-line history for the function's range.
    # We use the first node's line and end for the blame range.
    start_line = nodes[0]["line"]
    end_line = nodes[0]["end"]

    blame_data = ctx.git_blame(target_path, start_line, end_line)

    # 3. Aggregate the latest change info (newest date wins).
    # Since blame returns line-by-line, we'll track the latest commit/author for the whole block.
    latest_commit = None
    latest_date = "0000-00-00T00:00:00Z"
    latest_author = "Unknown"

    for entry in blame_data:
        # The date format from git_blame is ISO 8601, which sorts correctly as strings.
        entry_date = entry.get("date", "0000-00-00T00:00:00Z")
        if entry_date > latest_date:
            latest_date = entry_date
            latest_commit = entry.get("commit")
            latest_author = entry.get("author")

    return {
        "function_name": func_name,
        "path": target_path,
        "last_changed": {
            "date": latest_date,
            "author": latest_author,
            "commit_hash": latest_commit
        }
    }
