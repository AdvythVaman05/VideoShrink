from typing import List, Dict, Any

def render_timeline_barcode_html(timeline_data: List[Dict[str, Any]], num_bins: int = 100) -> str:
    """
    Renders an HTML/CSS dual barcode visualizer:
    1. Full baseline video timeline (dense representation)
    2. Selected frame distribution (showing sampling gaps and clusters)
    """
    if not timeline_data:
        return "<p>No timeline data available.</p>"

    total_items = len(timeline_data)
    bin_size = max(1, total_items // num_bins)

    # Calculate density for each bin
    bins_selected = []
    for b in range(num_bins):
        start = b * bin_size
        end = min(total_items, (b + 1) * bin_size)
        slice_items = timeline_data[start:end]
        if not slice_items:
            break
        has_sel = any(item.get("is_selected", False) for item in slice_items)
        has_cut = any(item.get("is_scene_cut", False) for item in slice_items)
        if has_cut:
            bins_selected.append("#E74C3C")  # Red for cut
        elif has_sel:
            bins_selected.append("#2ECC71")  # Green for retained
        else:
            bins_selected.append("#222831")  # Dark empty

    selected_bars = "".join(
        f'<div style="flex: 1; height: 26px; background-color: {color}; margin-right: 1px; border-radius: 1px;"></div>'
        for color in bins_selected
    )

    baseline_bars = "".join(
        f'<div style="flex: 1; height: 14px; background-color: #4A90E2; margin-right: 1px; border-radius: 1px;"></div>'
        for _ in range(len(bins_selected))
    )

    html = f"""
    <div style="font-family: monospace; background: #161b22; padding: 16px; border-radius: 8px; border: 1px solid #30363d;">
        <div style="margin-bottom: 6px; color: #8b949e; font-size: 12px; display: flex; justify-content: space-between;">
            <span>ORIGINAL VIDEO FRAMES (100% TEMPORAL DENSITY)</span>
            <span>{total_items} FRAMES EVALUATED</span>
        </div>
        <div style="display: flex; width: 100%; margin-bottom: 14px;">
            {baseline_bars}
        </div>
        <div style="margin-bottom: 6px; color: #8b949e; font-size: 12px; display: flex; justify-content: space-between;">
            <span>OPTIMIZED SELECTION BARCODE (SPARSE RETENTION MAP)</span>
            <span><span style="color:#2ECC71">■ Retained</span> &nbsp; <span style="color:#E74C3C">■ Transition</span> &nbsp; <span style="color:#30363d">■ Pruned</span></span>
        </div>
        <div style="display: flex; width: 100%;">
            {selected_bars}
        </div>
    </div>
    """
    return html
