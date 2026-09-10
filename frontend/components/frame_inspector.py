import streamlit as st
from typing import List, Dict, Any

def render_frame_inspector(preview_frames: List[Dict[str, Any]]) -> None:
    """
    Renders an interactive inspection gallery of selected frames
    displaying timestamp, motion score, similarity score, and explainable rationale.
    """
    if not preview_frames:
        st.info("No frame previews available for this run.")
        return

    st.markdown("### Explainable Keyframe Inspector")
    st.caption("Inspect sampled frames and the algorithmic rationale behind their retention.")

    # Grid layout
    cols_per_row = 4
    for i in range(0, len(preview_frames), cols_per_row):
        cols = st.columns(cols_per_row)
        for c_idx, frame_data in enumerate(preview_frames[i:i + cols_per_row]):
            with cols[c_idx]:
                thumb_b64 = frame_data.get("thumbnail_base64")
                if thumb_b64:
                    st.image(
                        f"data:image/jpeg;base64,{thumb_b64}",
                        use_container_width=True
                    )
                st.markdown(f"**Frame #{frame_data['frame_idx']}** ({frame_data['timestamp_formatted']})")
                
                motion = frame_data.get("motion_score")
                sim = frame_data.get("similarity_score")
                
                badges = []
                if motion is not None:
                    badges.append(f"Motion: `{motion:.2f}`")
                if sim is not None:
                    badges.append(f"Sim: `{sim:.2f}`")
                
                if badges:
                    st.caption(" | ".join(badges))
                
                st.markdown(f"> *{frame_data.get('selection_reason', 'Retained')}*")
