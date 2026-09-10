import altair as alt
import pandas as pd
from typing import List, Dict, Any

def create_motion_timeline_chart(timeline_data: List[Dict[str, Any]]) -> alt.Chart:
    """
    Creates an Altair time-series chart showing:
    - Motion score curve over time
    - Points representing selected frames (green) vs dropped frames (gray)
    - Scene cut indicators
    """
    if not timeline_data:
        return alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(text="No timeline data available")

    df = pd.DataFrame(timeline_data)
    df["Status"] = df["is_selected"].apply(lambda x: "Retained Frame" if x else "Dropped Frame")
    df["Time (s)"] = df["timestamp"].round(2)
    df["Motion Score"] = df["motion_score"].round(3)
    df["Similarity"] = df["similarity_score"].round(3)

    # Base line chart of motion score
    line = (
        alt.Chart(df)
        .mark_line(color="#4A90E2", strokeWidth=2, opacity=0.85)
        .encode(
            x=alt.X("Time (s):Q", title="Video Timeline (Seconds)"),
            y=alt.Y("Motion Score:Q", title="Motion Energy Score [0-1]", scale=alt.Scale(domain=[0, 1.05])),
            tooltip=["Time (s)", "Motion Score", "Similarity", "Status"]
        )
    )

    # Overlay points for kept frames
    points = (
        alt.Chart(df[df["is_selected"] == True])
        .mark_circle(size=45, opacity=0.9)
        .encode(
            x="Time (s):Q",
            y="Motion Score:Q",
            color=alt.Color(
                "is_scene_cut:N",
                scale=alt.Scale(domain=[False, True], range=["#2ECC71", "#E74C3C"]),
                legend=alt.Legend(title="Frame Type", labelExpr="datum.value ? 'Scene Transition' : 'Retained Frame'")
            ),
            tooltip=["Time (s)", "Motion Score", "Similarity", "Status"]
        )
    )

    chart = (line + points).properties(
        title="Temporal Motion Profile & Frame Selection Decisions",
        height=260
    ).interactive()

    return chart
