from typing import List, Tuple


def parse_sort_params(sort_by: str | None, sort_dir: str | None) -> List[Tuple[str, str]]:
    """Return a list of (column_name, dir) tuples from comma-separated inputs.

    dir is normalized to 'asc' or 'desc'. If no sort_by provided, default to
    [('created_at', 'desc')].
    """
    if not sort_by:
        return [('created_at', 'desc')]
    parts = [p.strip() for p in sort_by.split(',') if p.strip()]
    if not parts:
        return [('created_at', 'desc')]

    dirs: List[str] = []
    if sort_dir:
        dirs = [d.strip().lower() for d in sort_dir.split(',') if d.strip()]
    if not dirs:
        dirs = ['desc'] * len(parts)
    elif len(dirs) < len(parts):
        dirs = dirs + [dirs[-1]] * (len(parts) - len(dirs))

    valid_dirs = ('asc', 'desc')
    result: List[Tuple[str, str]] = []
    for name, d in zip(parts, dirs):
        if d not in valid_dirs:
            d = 'desc'
        result.append((name, d))
    return result
