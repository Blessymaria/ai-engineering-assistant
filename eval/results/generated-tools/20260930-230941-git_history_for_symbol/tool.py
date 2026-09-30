def run(args, ctx):
    import re

    # Extract the symbol's path from the node information
    # We assume the node found via list_nodes or search_code is the target.
    # Since the input is structured, we rely on file_path being correct.

    # Use git_log on the file path to get history for the whole file
    log_data = ctx.git_log(args['file_path'], limit=10)

    # Filter commits to see if the symbol name appears in the subject or if we can infer relevance.
    # Since git_log only gives file-level history, we'll return the general history
    # and let the consumer filter/interpret based on the symbol name.

    # For a more precise answer, we'd need a tool that can query history *per symbol*, 
    # but given the available tools, we use git_log on the file path.

    return {"file_path": args['file_path'], "symbol_name": args['symbol_name'], "history": log_data}
