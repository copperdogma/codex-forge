def normalize_start_seq(game_sections):
    """
    Ensure game_sections are strictly increasing by start_seq where present.
    Sort by (start_seq, id), push None start_seq to the end.
    """
    with_seq = [gs for gs in game_sections if gs.get("start_seq") is not None]
    without_seq = [gs for gs in game_sections if gs.get("start_seq") is None]
    with_seq_sorted = sorted(with_seq, key=lambda g: (g.get("start_seq"), g.get("id")))
    out = with_seq_sorted + without_seq
    return out
