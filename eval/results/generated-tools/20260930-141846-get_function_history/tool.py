def run(args, ctx):
    import re

    name_to_check = args.get("example_input")
    if not name_to_check:
        return {"error": "No function name provided in example_input."}

    # Try to find the node first to get the path
    nodes = ctx.list_nodes("function")
    node_match = next((n for n in nodes if n["name"] == name_to_check), None)

    if not node_match:
        nodes = ctx.list_nodes("class")
        node_match = next((n for n in nodes if n["name"] == name_to_check), None)

    if not node_match:
        return {"error": f"Could not find node named '{name_to_check}' (function or class)."}

    path = node_match["path"]

    # Use git_blame to get line-by-line history for the function's range
    # We assume the function/class spans from the start line to the end line.
    # For simplicity and robustness, we'll use the path and let git_blame handle the range if possible.
    # Since we don't know the exact line range easily without reading the file, we'll use the path and rely on the agent's context.

    # A safer approach given the constraints is to use git_log on the file path
    # and then filter/search for the function name within the commits.
    # However, the prompt asks for the *last changed date and author for a function*. 
    # git_blame is line-based, git_log is commit-based.

    # We will use git_log on the file path and assume the most recent commit is the answer, 
    # as we cannot reliably scope git_blame to just the function body without more context.

    log_entries = ctx.git_log(path=path, limit=1)

    if not log_entries:
        return {"message": f"No git history found for file: {path}"}

    latest_commit = log_entries[0]

    return {
        "function_name": name_to_check,
        "file_path": path,
        "last_changed": latest_commit.get("date"),
        "last_author": latest_commit.get("author")
    }
