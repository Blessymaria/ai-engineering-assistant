def run(args, ctx):
    import re

    # The user wants the git history for a specific function. 
    # ctx.git_log requires a path. We must use the file path associated with the function.
    # We assume the 'repository_path' argument points to the file containing the function.

    path_to_check = args.get("repository_path")
    func_name = args.get("function_name")

    if not path_to_check or not func_name:
        return {"error": "Missing repository_path or function_name in arguments."}

    # Use ctx.git_log on the file path provided.
    log_entries = ctx.git_log(path=path_to_check, limit=1)

    if not log_entries:
        return {"error": f"Could not retrieve git log for path: {path_to_check}. Check if the path is correct and the file exists."}

    # The latest commit is the first entry
    latest_commit = log_entries[0]

    # Check if the commit subject mentions the function name (heuristic)
    subject = latest_commit.get("subject", "")

    if func_name.lower() not in subject.lower() and func_name.lower() not in path_to_check.lower():
        # If the subject doesn't mention it, we still return the latest commit info for the repo.
        return {
            "message": f"Latest commit in {path_to_check} found, but subject does not explicitly mention '{func_name}'. Returning general repo history.",
            "latest_commit": {
                "date": latest_commit.get("date"),
                "author": latest_commit.get("author")
            }
        }

    return {
        "function": func_name,
        "repository": path_to_check,
        "last_change_date": latest_commit.get("date"),
        "last_author": latest_commit.get("author")
    }
